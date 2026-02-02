// 대시보드 로직

document.addEventListener('DOMContentLoaded', async () => {
    const token = localStorage.getItem('access_token');
    const landingView = document.getElementById('landing-view');
    const dashboardView = document.getElementById('dashboard-view');

    if (token) {
        // 로그인 상태: 대시보드 표시 및 데이터 로드
        if (landingView) landingView.style.display = 'none';
        if (dashboardView) dashboardView.style.display = 'block';

        await Promise.all([loadFolders(), loadMeetings()]);
        setupUpload();
        setupDragAndDrop();
    } else {
        // 비로그인 상태: 랜딩 페이지 유지
        if (landingView) landingView.style.display = 'block';
        if (dashboardView) dashboardView.style.display = 'none';
    }
});

let allMeetings = [];
let currentFilter = 'all'; // 'all', 'unclassified', or folderId (int)

async function loadFolders() {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch('/api/folders/', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (response.ok) {
            const folders = await response.json();
            renderFolders(folders);
        }
    } catch (e) {
        console.error("Failed to load folders", e);
    }
}

function renderFolders(folders) {
    const list = document.getElementById('folder-list');
    list.innerHTML = folders.map(folder => `
        <div class="folder-item ${currentFilter === folder.id ? 'active' : ''}" 
             ondrop="drop(event, ${folder.id})" ondragover="allowDrop(event)"
             onclick="filterMeetings(${folder.id})">
            <span><i class="fa-regular fa-folder" style="margin-right: 8px;"></i> ${folder.name}</span>
            <div class="folder-actions" onclick="event.stopPropagation()">
                <button class="folder-btn-sm" onclick="deleteFolder(${folder.id})" title="삭제"><i class="fa-solid fa-trash"></i></button>
            </div>
        </div>
    `).join('');
}

async function createFolder() {
    const name = prompt("새 폴더 이름을 입력하세요:");
    if (!name) return;

    const token = localStorage.getItem('access_token');
    const res = await fetch('/api/folders/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ name })
    });

    if (res.ok) {
        loadFolders();
    } else {
        alert("폴더 생성 실패");
    }
}

async function deleteFolder(id) {
    if (!confirm("폴더를 삭제하시겠습니까? (내용물은 유지됩니다)")) return;

    const token = localStorage.getItem('access_token');
    await fetch(`/api/folders/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
    });
    loadFolders();
    if (currentFilter === id) filterMeetings('all');
}

function filterMeetings(filter) {
    currentFilter = filter;

    // UI Active State Update
    document.querySelectorAll('.menu-item, .folder-item').forEach(el => el.classList.remove('active'));

    if (filter === 'all') {
        document.querySelector('[data-filter="all"]').classList.add('active');
        document.getElementById('page-title').innerHTML = '<i class="fa-solid fa-layer-group"></i> 전체 회의';
    } else if (filter === 'unclassified') {
        document.querySelector('[data-filter="unclassified"]').classList.add('active');
        document.getElementById('page-title').innerHTML = '<i class="fa-regular fa-folder"></i> 미분류';
    } else {
        // Folder active state needs to be handled in renderFolders or re-render
        renderFolders(document.querySelectorAll('.folder-item').length ? [] : []); // Re-render to update active class (simplified)
        // Better: Find the element by text or ID in DOM. For now re-load folders is safe or just styling.
        loadFolders(); // Re-fetch to apply 'active' class correctly in render
    }

    renderMeetingList(allMeetings);
}

// meeting.py에서 loadMeetings 수정 필요: 전역 변수 allMeetings에 저장
async function loadMeetings() {
    const list = document.getElementById('meeting-list');
    list.innerHTML = '<div class="loading-state"><i class="fa-solid fa-circle-notch fa-spin"></i><p>불러오는 중...</p></div>';

    try {
        const token = localStorage.getItem('access_token');
        const res = await fetch('/api/meeting/', {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (res.ok) {
            allMeetings = await res.json();
            renderMeetingList(allMeetings);
        } else {
            list.innerHTML = '<div class="empty-state"><p>회의 목록을 불러오지 못했습니다.</p></div>';
        }
    } catch (e) {
        console.error(e);
        list.innerHTML = '<div class="empty-state"><p>오류가 발생했습니다.</p></div>';
    }
}

function renderMeetingList(meetings) {
    const list = document.getElementById('meeting-list');
    let filtered = meetings;

    if (currentFilter !== 'all') {
        if (currentFilter === 'unclassified') {
            filtered = meetings.filter(m => !m.folder_id);
        } else {
            filtered = meetings.filter(m => m.folder_id === currentFilter);
        }
    }

    if (filtered.length === 0) {
        list.innerHTML = '<div class="empty-state"><p>이 폴더에 회의가 없습니다.</p></div>';
        return;
    }

    list.innerHTML = filtered.map(meeting => `
        <div class="meeting-card" draggable="true" ondragstart="drag(event, ${meeting.id})">
            <button class="btn-delete" onclick="deleteMeeting(event, ${meeting.id})">
                <i class="fa-solid fa-trash"></i>
            </button>
            <div onclick="location.href='/meeting/${meeting.id}'">
                <div class="meeting-title">${meeting.title}</div>
                <div class="meeting-date">${new Date(meeting.created_at).toLocaleString()}</div>
                <span class="meeting-status status-${meeting.status}">
                    ${meeting.status === 'completed' ? '완료' : (meeting.status === 'processing' ? '분석중' : '대기중')}
                </span>
            </div>
        </div>
    `).join('');
}

// Drag and Drop
function allowDrop(ev) {
    ev.preventDefault();
}

function drag(ev, meetingId) {
    ev.dataTransfer.setData("meetingId", meetingId);
}

async function drop(ev, folderId) {
    ev.preventDefault();
    const meetingId = ev.dataTransfer.getData("meetingId");

    // API Call to move meeting
    const token = localStorage.getItem('access_token');
    const res = await fetch(`/api/folders/${folderId}/meetings/${meetingId}`, {
        method: 'PUT',
        headers: { 'Authorization': `Bearer ${token}` }
    });

    if (res.ok) {
        // Update local data
        const meeting = allMeetings.find(m => m.id == meetingId);
        if (meeting) meeting.folder_id = folderId;
        renderMeetingList(allMeetings); // Refresh view
    } else {
        alert("이동 실패");
    }
}

function setupDragAndDrop() {
    // Drop zone for 'Unclassified'
    const unclassifiedBtn = document.querySelector('[data-filter="unclassified"]');
    if (unclassifiedBtn) {
        unclassifiedBtn.ondragover = allowDrop;
        unclassifiedBtn.ondrop = (ev) => drop(ev, 0); // 0 for unclassified
    }
}

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

        // 이름 길이에 따라 글자 크기 조절
        let fontSize = '1.2rem';
        if (title.length > 30) fontSize = '0.9rem';
        else if (title.length > 20) fontSize = '1.0rem';
        else if (title.length > 12) fontSize = '1.1rem';

        return `
            <div class="meeting-card" onclick="location.href='/meeting/${meeting.id}'">
                <button class="btn-delete" onclick="deleteMeeting(event, ${meeting.id})" title="회의 삭제">
                    <i class="fa-solid fa-trash"></i>
                </button>
                <div class="meeting-title" id="title-container-${meeting.id}" style="display:flex; align-items:center; gap:8px; min-height: 30px;">
                    <span id="title-text-${meeting.id}" style="font-size: ${fontSize}">${title}</span>
                    <button class="btn-edit" id="btn-edit-${meeting.id}" onclick="enableEditMode(event, ${meeting.id})" title="이름 변경" style="background:none; border:none; cursor: pointer; color: #888; font-size: 0.9rem;">
                        <i class="fa-solid fa-pen"></i>
                    </button>
                </div>
                <div class="meeting-date"><i class="fa-regular fa-clock"></i> ${date}</div>
                <span class="meeting-status ${statusClass}">
                    ${(meeting.status || 'unknown').toUpperCase()}
                </span>
            </div>
        `;
    }).join('');
}

function enableEditMode(event, meetingId) {
    event.stopPropagation();
    const container = document.getElementById(`title-container-${meetingId}`);
    const textSpan = document.getElementById(`title-text-${meetingId}`);
    const editBtn = document.getElementById(`btn-edit-${meetingId}`);

    if (!container || !textSpan || !editBtn) return;

    const currentTitle = textSpan.innerText;

    textSpan.style.display = 'none';
    editBtn.style.display = 'none';

    const input = document.createElement('input');
    input.type = 'text';
    input.value = currentTitle;
    input.className = 'edit-title-input';
    input.style.width = '100%';
    input.style.maxWidth = '100%'; // Prevent overflow
    input.style.boxSizing = 'border-box'; // Include padding/border in width
    input.style.padding = '4px 8px';
    input.style.fontSize = '1rem';
    input.style.borderRadius = '4px';
    input.style.border = '1px solid #3b82f6'; // Primary color
    input.style.background = '#0f172a'; // bg-dark
    input.style.color = '#f8fafc'; // text-main
    input.style.outline = 'none';

    input.onclick = (e) => e.stopPropagation();

    let methodCalled = false;
    const finish = async (save) => {
        if (methodCalled) return;
        methodCalled = true;
        if (save) {
            await saveMeetingTitle(meetingId, input.value, currentTitle);
        } else {
            cancelEditMode(meetingId, currentTitle);
        }
    }

    input.onkeydown = (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            input.blur(); // This will trigger onblur, which calls finish(true)
        } else if (e.key === 'Escape') {
            e.preventDefault();
            finish(false);
        }
    };

    input.onblur = () => finish(true);

    container.appendChild(input);
    input.focus();
}

function cancelEditMode(meetingId, originalTitle) {
    const container = document.getElementById(`title-container-${meetingId}`);
    const textSpan = document.getElementById(`title-text-${meetingId}`);
    const editBtn = document.getElementById(`btn-edit-${meetingId}`);
    const input = container.querySelector('input');

    if (input) input.remove();
    if (textSpan) {
        textSpan.innerText = originalTitle;
        textSpan.style.display = '';
    }
    if (editBtn) editBtn.style.display = '';
}

async function saveMeetingTitle(meetingId, newTitle, originalTitle) {
    if (!newTitle || !newTitle.trim()) {
        alert("제목을 입력해주세요.");
        cancelEditMode(meetingId, originalTitle);
        return;
    }

    if (newTitle === originalTitle) {
        cancelEditMode(meetingId, originalTitle);
        return;
    }

    // UI Update (Optimistic-ish: disable input)
    const container = document.getElementById(`title-container-${meetingId}`);
    const input = container ? container.querySelector('input') : null;
    if (input) input.disabled = true;

    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`/api/meeting/${meetingId}`, {
            method: 'PUT',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ title: newTitle })
        });

        if (response.ok) {
            await loadMeetings(); // 목록 갱신 (전체 리로드)
        } else {
            const error = await response.json();
            alert('이름 변경 실패: ' + (error.detail || '알 수 없는 오류'));
            cancelEditMode(meetingId, originalTitle);
        }
    } catch (err) {
        console.error(err);
        alert('이름 변경 중 오류가 발생했습니다.');
        cancelEditMode(meetingId, originalTitle);
    }
}

async function deleteMeeting(event, meetingId) {
    event.stopPropagation(); // 카드 클릭 이벤트 전파 방지

    if (!confirm("정말 이 회의를 삭제하시겠습니까?\\n삭제된 데이터는 복구할 수 없습니다.")) {
        return;
    }

    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`/api/meeting/${meetingId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (response.ok) {
            // alert('회의가 삭제되었습니다.'); // 너무 방해될 수 있으므로 생략 가능
            await loadMeetings(); // 목록 갱신
        } else {
            const error = await response.json();
            alert('삭제 실패: ' + (error.detail || '알 수 없는 오류'));
        }
    } catch (err) {
        console.error(err);
        alert('삭제 중 오류가 발생했습니다.');
    }
}
