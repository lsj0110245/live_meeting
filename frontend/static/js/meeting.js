// 회의 상세 페이지 로직

const meetingId = window.location.pathname.split('/').pop();

document.addEventListener('DOMContentLoaded', async () => {
    const token = localStorage.getItem('access_token');
    if (!token) { window.location.href = '/login'; return; }

    await loadMeetingDetails();

    const summaryBtn = document.getElementById('btn-summary');
    if (summaryBtn) {
        summaryBtn.addEventListener('click', generateSummary);
    }
});

async function loadMeetingDetails() {
    const token = localStorage.getItem('access_token');
    try {
        const response = await fetch(`/api/meeting/${meetingId}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) { alert('회의 정보를 불러올 수 없습니다.'); return; }

        const meeting = await response.json();

        document.getElementById('meeting-title').innerText = meeting.title;
        document.getElementById('meeting-date').innerText = new Date(meeting.created_at).toLocaleString();
        document.getElementById('meeting-desc').innerText = meeting.description || '설명 없음';

        if (meeting.audio_file_path) {
            // DB 경로 예: "media/recordings/audio/xxx.mp3" 또는 "/app/media/..."
            // "media/" 이후의 경로를 추출하여 URL 생성
            let relativePath = meeting.audio_file_path;
            if (relativePath.includes('media')) {
                relativePath = relativePath.split('media')[1];
                // split 후: ["", "/recordings/audio/xxx.mp3"] (lead slash might be present)
            }
            // 윈도우 경로 역슬래시 처리
            relativePath = relativePath.replace(/\\/g, '/');
            if (relativePath.startsWith('/')) relativePath = relativePath.substring(1);

            const player = document.getElementById('audio-player');
            if (player) {
                player.src = `/media/${relativePath}`;

                // 디버깅용 이벤트 리스너
                player.addEventListener('error', (e) => {
                    console.error("Audio Load Error:", player.error);
                    alert(`오디오 로드 실패: ${player.error.message || '알 수 없는 오류'}`);
                });

                player.addEventListener('loadedmetadata', () => {
                    console.log("Audio Metadata Loaded. Duration:", player.duration);
                });
            }
        }

        const transcriptList = document.getElementById('transcript-list');
        if (transcriptList) {
            if (meeting.transcripts && meeting.transcripts.length > 0) {
                transcriptList.innerHTML = ''; // 초기화

                meeting.transcripts.forEach(t => {
                    // 시간 포맷팅 (초 -> mm:ss)
                    const formatTime = (seconds) => {
                        const m = Math.floor(seconds / 60);
                        const s = Math.floor(seconds % 60);
                        return `${m}:${s.toString().padStart(2, '0')}`;
                    };

                    const item = document.createElement('div');
                    item.className = 'transcript-item';
                    item.innerHTML = `
                        <div class="time" onclick="seekAudio(${t.start_time})" style="cursor:pointer; color:#007bff; font-weight:bold;">
                            ${formatTime(t.start_time)}
                        </div>
                        <div class="content">
                            <span class="speaker" style="font-weight:bold; margin-right:5px;">${t.speaker}:</span>
                            ${t.text}
                        </div>
                    `;
                    transcriptList.appendChild(item);
                });
            } else {
                transcriptList.innerHTML = '<p class="placeholder-text">전사 데이터가 없습니다.</p>';
            }
        }

        // 요약본 로딩 로직
        if (meeting.summaries && meeting.summaries.length > 0) {
            // 가장 최근 요약 사용 (또는 리스트로 보여주기)
            const latestSummary = meeting.summaries[meeting.summaries.length - 1];
            const summaryContent = document.getElementById('summary-content');

            // 마크다운 렌더링 (간단히 텍스트로 처리하거나 marked 라이브러리 필요)
            // 여기서는 줄바꿈 처리만 간단히 구현
            let htmlContent = latestSummary.content.replace(/\n/g, '<br>');

            summaryContent.innerHTML = htmlContent;
        } else if (meeting.summary) {
            // 단일 객체로 올 경우 (Schema 구조에 따라 다름)
            const summaryContent = document.getElementById('summary-content');
            summaryContent.innerText = meeting.summary.content;
        }

    } catch (err) {
        console.error(err);
    }
}

async function generateSummary() {
    const token = localStorage.getItem('access_token');
    if (!confirm('AI 회의록 생성을 시작하시겠습니까?')) return;

    try {
        const response = await fetch(`/api/meeting/${meetingId}/summarize`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (response.ok) {
            alert('요약 요청이 완료되었습니다. 잠시 후 새로고침해주세요.');
        } else {
            alert('요청 실패');
        }
    } catch (err) {
        console.error(err);
    }
}

function exportMeeting(format) {
    const token = localStorage.getItem('access_token');
    window.location.href = `/api/export/${meetingId}?format=${format}&token=${token}`;
}
// 전역 스코프로 노출 (HTML onclick에서 사용)
window.exportMeeting = exportMeeting;
