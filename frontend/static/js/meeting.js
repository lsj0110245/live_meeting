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
            const filename = meeting.audio_file_path.split(/[\\/]/).pop();
            const player = document.getElementById('audio-player');
            if (player) {
                player.src = `/static/media/${filename}`;
            }
        }

        const transcriptList = document.getElementById('transcript-list');
        if (transcriptList) {
            transcriptList.innerHTML = '<p class="placeholder-text">전사 데이터 조회 API가 필요합니다.</p>';
        }

        // 요약본 로딩 로직 (Summary 필드가 있다면)
        // if (meeting.summary) { ... }

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
