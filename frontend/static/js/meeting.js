// 회의 상세 페이지 로직

const meetingId = window.location.pathname.split('/').pop();
let currentExportFormat = null;
let currentMeetingData = {}; // 현재 회의 데이터 저장용

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
        currentMeetingData = meeting; // 데이터 저장

        document.getElementById('meeting-title').innerText = meeting.title;
        document.getElementById('meeting-date').innerText = new Date(meeting.meeting_date || meeting.created_at).toLocaleString(); // meeting_date 우선 사용
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
                    item.style.cursor = 'pointer';
                    item.onclick = () => seekAudio(t.start_time);

                    item.innerHTML = `
                        <div class="time" style="color:#007bff; font-weight:bold;">
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
        if (meeting.summary) {
            const summaryContent = document.getElementById('summary-content');
            if (summaryContent) {
                // 줄바꿈 처리
                let htmlContent = meeting.summary.content.replace(/\n/g, '<br>');
                summaryContent.innerHTML = htmlContent;
            }
        }

    } catch (err) {
        console.error(err);
    }
}

// 오디오 재생 위치 이동
function seekAudio(time) {
    const player = document.getElementById('audio-player');
    if (player) {
        player.currentTime = time;
        if (player.paused) {
            player.play().catch(e => console.log('Auto-play blocked or failed:', e));
        }
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

// 메타데이터 모달 표시 (내보내기 전 수정)
function showMetadataModal(format) {
    currentExportFormat = format;
    const modal = document.getElementById('metadata-modal');

    // 현재 데이터로 폼 채우기
    if (currentMeetingData) {
        document.getElementById('meeting-title-input').value = currentMeetingData.title || '';
        document.getElementById('meeting-type-input').value = currentMeetingData.meeting_type || '';
        document.getElementById('meeting-date-input').value = currentMeetingData.meeting_date ? currentMeetingData.meeting_date.substring(0, 16) : '';
        document.getElementById('meeting-attendees-input').value = currentMeetingData.attendees || '';
        document.getElementById('meeting-writer-input').value = currentMeetingData.writer || '';
    }

    // 편집 가능하도록 설정 (READONLY 해제)
    const dateInput = document.getElementById('meeting-date-input');
    dateInput.removeAttribute('readonly');
    dateInput.style.backgroundColor = '';
    dateInput.style.cursor = '';

    // 버튼 텍스트와 동작 변경
    const submitBtn = document.getElementById('metadata-submit-btn');
    if (submitBtn) {
        submitBtn.textContent = "저장 후 내보내기";
        submitBtn.onclick = submitMetadataAndExport;
    }

    // 모달 닫기 버튼에도 이벤트 연결 (필요 시)
    // 보통 모달 내부의 닫기 버튼은 onclick="closeMetadataModal()"로 되어 있을 것임.

    modal.style.display = 'flex';
}

function closeMetadataModal() {
    const modal = document.getElementById('metadata-modal');
    if (modal) modal.style.display = 'none';
    currentExportFormat = null;
}

// 메타데이터 저장 후 내보내기
async function submitMetadataAndExport() {
    const form = document.getElementById('metadata-form');
    // HTML5 유효성 검사 (required 등)
    if (!form.checkValidity()) {
        form.reportValidity(); // 브라우저 기본 알림 표시
        return;
    }

    const updateData = {
        title: document.getElementById('meeting-title-input').value.trim(),
        meeting_type: document.getElementById('meeting-type-input').value.trim(),
        meeting_date: document.getElementById('meeting-date-input').value || null, // datetime-local format or null
        attendees: document.getElementById('meeting-attendees-input').value.trim(),
        writer: document.getElementById('meeting-writer-input').value.trim()
    };

    const token = localStorage.getItem('access_token');

    try {
        // 1. 메타데이터 업데이트 API 호출
        const updateResponse = await fetch(`/api/meeting/${meetingId}`, {
            method: 'PUT',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(updateData)
        });

        if (!updateResponse.ok) {
            const errorData = await updateResponse.json();
            throw new Error(errorData.detail || '메타데이터 업데이트 실패');
        }

        // 최신 데이터로 로컬 갱신
        const updatedMeeting = await updateResponse.json();
        currentMeetingData = updatedMeeting;

        // UI 타이틀 업데이트 등 필요하다면 수행
        document.getElementById('meeting-title').innerText = updatedMeeting.title;

        alert('회의 정보가 수정되었습니다. 다운로드를 시작합니다.');

        // 포맷 저장 (closeMetadataModal에서 초기화되므로)
        const formatToExport = currentExportFormat;
        closeMetadataModal();

        // 2. 내보내기 실행
        if (formatToExport) {
            await executeExport(formatToExport);
        }

    } catch (err) {
        console.error('Error:', err);
        alert('오류가 발생했습니다: ' + err.message);
    }
}

async function executeExport(format) {
    const token = localStorage.getItem('access_token');

    // Show Loading
    showLoading('파일을 생성하고 있습니다...');

    try {
        const response = await fetch(`/api/export/${meetingId}?format=${format}`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            hideLoading();
            alert('내보내기 실패: ' + response.statusText);
            return;
        }

        // Blob으로 변환
        const blob = await response.blob();

        hideLoading();

        // 다운로드 링크 생성
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;

        // 파일명 추출 (Content-Disposition 헤더가 있다면 베스트, 아니면 날짜 기반)
        const dateStr = new Date().toISOString().slice(0, 10);
        a.download = `meeting_export_${dateStr}.${format === 'excel' ? 'xlsx' : 'csv'}`;

        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);

    } catch (err) {
        console.error('Export error:', err);
        alert('내보내기 중 오류가 발생했습니다.');
    }
}

// exportMeeting 함수 수정: 모달 열기
function exportMeeting(format) {
    showMetadataModal(format);
}

// 전역 스코프로 노출 (HTML onclick에서 사용)
window.exportMeeting = exportMeeting;
window.closeMetadataModal = closeMetadataModal;
window.submitMetadataAndExport = submitMetadataAndExport;
window.seekAudio = seekAudio;
