// 대시보드 로직

document.addEventListener('DOMContentLoaded', async () => {
    const token = localStorage.getItem('access_token');
    const landingView = document.getElementById('landing-view');
    const dashboardView = document.getElementById('dashboard-view');

    if (token) {
        // 로그인 상태: 대시보드 표시 및 데이터 로드
        if (landingView) landingView.style.display = 'none';
        if (dashboardView) dashboardView.style.display = 'block';

        await loadMeetings();
        setupUpload();
    } else {
        // 비로그인 상태: 랜딩 페이지 유지 (아무것도 하지 않음)
        // common.js의 리다이렉트 로직이 있다면 그것을 무효화해야 할 수도 있음 (현재 common.js는 checkLoginStatus만 수행하고 자동 리다이렉트는 안 함)
        if (landingView) landingView.style.display = 'block';
        if (dashboardView) dashboardView.style.display = 'none';
    }
});

function setupUpload() {
    const fileInput = document.getElementById('file-input');
    const uploadBtn = document.getElementById('btn-upload');

    if (uploadBtn && fileInput) {
        uploadBtn.addEventListener('click', () => {
            fileInput.click();
        });

        fileInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            const formData = new FormData();
            formData.append('file', file);

            if (!confirm(`'${file.name}' 파일을 업로드하시겠습니까?`)) return;

            try {
                alert('업로드를 시작합니다.');
                const token = localStorage.getItem('access_token');

                const response = await fetch('/api/upload/file', {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${token}`
                    },
                    body: formData
                });

                if (response.ok) {
                    alert('업로드 성공! 분석이 곧 시작됩니다.');
                    await loadMeetings(); // 목록 갱신
                } else {
                    const error = await response.json();
                    alert('실패: ' + error.detail);
                }
            } catch (err) {
                console.error(err);
                alert('업로드 중 오류가 발생했습니다.');
            }

            fileInput.value = '';
        });
    }
}

async function loadMeetings() {
    const listEl = document.getElementById('meeting-list');
    if (!listEl) return;

    const token = localStorage.getItem('access_token');

    try {
        const response = await fetch('/api/meeting', {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (response.ok) {
            const meetings = await response.json();
            renderMeetings(meetings);
        } else if (response.status === 401) {
            window.location.href = '/login';
        } else {
            listEl.innerHTML = '<div class="loading-state">목록을 불러오지 못했습니다.</div>';
        }
    } catch (error) {
        console.error(error);
        listEl.innerHTML = '<div class="loading-state">서버 연결 오류</div>';
    }
}

function renderMeetings(meetings) {
    const listEl = document.getElementById('meeting-list');

    if (meetings.length === 0) {
        listEl.innerHTML = `
            <div class="empty-state">
                <p>아직 회의가 없습니다.</p>
                <p style="margin-top:10px; font-size:0.9rem;">새 회의를 시작하거나 녹음 파일을 업로드해보세요.</p>
            </div>
        `;
        return;
    }

    listEl.innerHTML = meetings.map(meeting => {
        const date = new Date(meeting.created_at).toLocaleString();
        let statusClass = 'status-completed';
        if (meeting.status === 'recording') statusClass = 'status-recording';
        if (meeting.status === 'processing') statusClass = 'status-processing';

        const title = meeting.title || '제목 없는 회의';

        return `
            <div class="meeting-card" onclick="location.href='/meeting/${meeting.id}'">
                <div class="meeting-title">${title}</div>
                <div class="meeting-date"><i class="fa-regular fa-clock"></i> ${date}</div>
                <span class="meeting-status ${statusClass}">
                    ${(meeting.status || 'unknown').toUpperCase()}
                </span>
            </div>
        `;
    }).join('');
}
