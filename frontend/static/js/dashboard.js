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
let allFolders = []; // Store folders for dropdown
let currentFilter = 'all'; // 'all', 'unclassified', or folderId (int)
let selectedMeetingIds = new Set();
let selectedFile = null; // 파일 업로드용 전역 변수
let activeProcessingIds = new Set(); // 진행 중인 회의 ID 추적

// 진행률 폴링 시작 (1초마다)
setInterval(updateProgressBars, 1000);

async function loadFolders() {
    try {
        const token = localStorage.getItem('access_token');
        if (!token) return;

        const response = await fetch('/api/folders/', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (response.ok) {
            const folders = await response.json();
            allFolders = folders; // Store for bulk actions
            renderFolders(folders);
            updateBulkUI(); // Update dropdown if selection exists
            handleInitialRoute(); // Check URL for folder deep link
        } else if (response.status === 401 || response.status === 403) {
            window.location.href = '/login';
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
                <button class="folder-btn-sm" id="btn-edit-folder-${folder.id}" onclick="enableFolderEditMode(event, ${folder.id})" title="이름 변경"><i class="fa-solid fa-pen"></i></button>
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

function enableFolderEditMode(event, folderId) {
    event.stopPropagation();
    const folderItem = event.target.closest('.folder-item');
    const span = folderItem.querySelector('span');
    const actions = folderItem.querySelector('.folder-actions');

    if (!span || !actions) return;

    // 현재 이름 가져오기 (아이콘 제외)
    const currentName = span.innerText.trim();

    // UI 숨김
    span.style.display = 'none';
    actions.style.display = 'none';

    // 입력창 생성
    const input = document.createElement('input');
    input.type = 'text';
    input.value = currentName;
    input.className = 'edit-folder-input';
    input.style.width = '120px'; // 적절한 너비
    input.style.padding = '2px 5px';
    input.style.fontSize = '0.9rem';
    input.style.border = '1px solid #3b82f6';
    input.style.borderRadius = '4px';
    input.style.background = '#1e293b';
    input.style.color = '#fff';
    input.style.outline = 'none';

    input.onclick = (e) => e.stopPropagation();

    let methodCalled = false;
    const finish = async (save) => {
        if (methodCalled) return;
        methodCalled = true;

        if (save) {
            await saveFolderName(folderId, input.value, currentName);
        } else {
            cancelFolderEditMode(folderItem, span, actions);
        }
    };

    input.onkeydown = (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            input.blur();
        } else if (e.key === 'Escape') {
            e.preventDefault();
            finish(false);
        }
    };

    input.onblur = () => finish(true);

    // span 앞에 삽입 (prepend)
    folderItem.insertBefore(input, actions);
    input.focus();
}

function cancelFolderEditMode(folderItem, span, actions) {
    const input = folderItem.querySelector('input');
    if (input) {
        try {
            input.remove();
        } catch (e) {
            // Already removed or detached
        }
    }
    span.style.display = '';
    actions.style.display = '';
}

async function saveFolderName(folderId, newName, originalName) {
    if (!newName || !newName.trim() || newName === originalName) {
        // 복구
        const folderItem = document.querySelector(`.folder-item[onclick*="filterMeetings(${folderId})"]`);
        if (folderItem) {
            const span = folderItem.querySelector('span');
            const actions = folderItem.querySelector('.folder-actions');
            cancelFolderEditMode(folderItem, span, actions);
        }
        return;
    }

    try {
        const token = localStorage.getItem('access_token');
        const res = await fetch(`/api/folders/${folderId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ name: newName })
        });

        if (res.ok) {
            loadFolders(); // Reload triggers re-render

            // Update URL if this folder is current
            if (currentFilter === folderId) {
                history.replaceState({ folderId: folderId }, '', `/folders/${encodeURIComponent(newName)}`);
                const title = document.getElementById('page-title');
                if (title) title.innerHTML = `<i class="fa-regular fa-folder"></i> ${newName}`;
            }

        } else {
            alert("폴더 이름 변경 실패");
            loadFolders(); // Revert UI check
        }
    } catch (e) {
        console.error(e);
        alert("오류 발생");
        loadFolders();
    }
}

function filterMeetings(filter, pushState = true) {
    currentFilter = filter;

    // UI Active State: Reset all first
    document.querySelectorAll('.menu-item, .folder-item').forEach(el => el.classList.remove('active'));

    const title = document.getElementById('page-title');

    if (filter === 'all') {
        const btn = document.querySelector('[data-filter="all"]');
        if (btn) btn.classList.add('active');
        if (title) title.innerHTML = '<i class="fa-solid fa-layer-group"></i> 전체 회의';
        if (pushState) history.pushState({ filter: 'all' }, '', '/');

    } else if (filter === 'unclassified') {
        const btn = document.querySelector('[data-filter="unclassified"]');
        if (btn) btn.classList.add('active');
        if (title) title.innerHTML = '<i class="fa-regular fa-folder"></i> 미분류';
        // Unclassified URL?? Maybe /unclassified or just query param? 
        // User didn't specify, keeping it simple or maybe /folders/unclassified?
        // Let's stick to no URL change for unclassified for now unless requested, or match pattern
        // The user asked for /test (folder name). Unclassified is special.
        // Let's try /folders/unclassified conceptually but we need to handle "unclassified" name collision.
        // For now, let's keep root or add query param ?filter=unclassified
        if (pushState) history.pushState({ filter: 'unclassified' }, '', '/?filter=unclassified');

    } else {
        // Specific Folder
        const folder = allFolders.find(f => f.id === filter);
        if (folder) {
            if (title) title.innerHTML = `<i class="fa-regular fa-folder"></i> ${folder.name}`;
            if (pushState) history.pushState({ folderId: filter }, '', `/folders/${encodeURIComponent(folder.name)}`);
        }

        // Re-render folder list to update active class
        renderFolders(allFolders);
    }

    renderMeetingList(allMeetings);

    // Show/Hide Remove Button
    updateBulkUI();
}

// Initial URL Check
async function handleInitialRoute() {
    const path = window.location.pathname;
    const decodedPath = decodeURIComponent(path);

    if (decodedPath.startsWith('/folders/')) {
        const folderName = decodedPath.split('/folders/')[1];
        if (folderName) {
            // Find folder by name
            const folder = allFolders.find(f => f.name === folderName);
            if (folder) {
                filterMeetings(folder.id, false); // Don't push state again
                return;
            }
        }
    }

    // Check query param for unclassified
    const params = new URLSearchParams(window.location.search);
    if (params.get('filter') === 'unclassified') {
        filterMeetings('unclassified', false);
        return;
    }

    // Default to 'all' if no specific route is matched
    filterMeetings('all', false);
}

// History Back/Forward
window.addEventListener('popstate', (event) => {
    if (event.state) {
        if (event.state.folderId) {
            filterMeetings(event.state.folderId, false);
        } else if (event.state.filter === 'all') {
            filterMeetings('all', false);
        } else if (event.state.filter === 'unclassified') {
            filterMeetings('unclassified', false);
        }
    } else {
        // Handle no state (maybe initial load or external nav)
        // Usually rerunning route check or default to all
        handleInitialRoute();
    }
});

// Bulk & Selection Logic
function toggleSelection(event, id) {
    event.stopPropagation();
    const checkbox = document.getElementById(`check-meeting-${id}`);

    if (selectedMeetingIds.has(id)) {
        selectedMeetingIds.delete(id);
        if (checkbox) {
            checkbox.classList.remove('checked');
            checkbox.style.color = '#94a3b8'; // text-sub
        }
    } else {
        selectedMeetingIds.add(id);
        if (checkbox) {
            checkbox.classList.add('checked');
            checkbox.style.color = '#3b82f6'; // primary
        }
    }
    updateBulkUI();
}

function updateBulkUI() {
    const bulkActions = document.getElementById('bulk-actions');
    const countSpan = document.getElementById('selected-count');
    const dropdown = document.getElementById('move-to-dropdown');
    const btnRemove = document.getElementById('btn-remove-from-list');

    if (selectedMeetingIds.size > 0 && bulkActions) {
        bulkActions.style.display = 'flex';
        if (countSpan) countSpan.innerText = `${selectedMeetingIds.size}개 선택됨`;

        // Show "Remove from List" only if inside a specific folder
        if (typeof currentFilter === 'number' && btnRemove) {
            btnRemove.style.display = 'inline-block';
        } else if (btnRemove) {
            btnRemove.style.display = 'none';
        }

        // Update Dropdown
        if (dropdown) {
            dropdown.innerHTML = `
                <a href="#" onclick="moveSelectedToFolder(0); return false;">
                    <i class="fa-regular fa-folder"></i> 미분류로 이동
                </a>
                ${allFolders.map(f => `
                    <a href="#" onclick="moveSelectedToFolder(${f.id}); return false;">
                         <i class="fa-regular fa-folder"></i> ${f.name}
                    </a>
                `).join('')}
            `;
        }
    } else if (bulkActions) {
        bulkActions.style.display = 'none';
    }
}

async function removeFromList() {
    if (selectedMeetingIds.size === 0) return;

    const ids = Array.from(selectedMeetingIds);
    // Confirmation
    if (!confirm(`선택한 ${ids.length}개의 회의를 이 폴더에서 제거하시겠습니까?\n(제거된 회의는 '미분류'로 이동됩니다)`)) return;

    // Use existing move logic to move to Unclassified (0)
    // We can reuse moveSelectedToFolder but we might want to skip the prompt inside it?
    // moveSelectedToFolder(0) asks for confirmation.
    // Let's call the API directly or refactor moveSelectedToFolder.
    // To avoid double confirmation, implementing direct call here:

    try {
        const token = localStorage.getItem('access_token');
        const res = await fetch(`/api/folders/0/meetings`, {
            method: 'PUT',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(ids)
        });

        if (res.ok) {
            selectedMeetingIds.clear();
            updateBulkUI();

            // Reload logic handles the view update
            // Since we are inside a folder, removing them means they disappear from current view

            // Optimistic update for better UX?
            ids.forEach(id => {
                const m = allMeetings.find(m => m.id === id);
                if (m) m.folder_id = null; // Unclassified
            });
            renderMeetingList(allMeetings);

            // Or just loadMeetings to be safe
            // loadMeetings(); 
        } else {
            alert("제거 실패");
        }
    } catch (e) {
        console.error(e);
        alert("오류 발생");
    }
}

async function moveSelectedToFolder(folderId) {
    if (selectedMeetingIds.size === 0) return;

    const ids = Array.from(selectedMeetingIds);
    if (!confirm(`${ids.length}개의 회의를 이동하시겠습니까?`)) return;

    try {
        const token = localStorage.getItem('access_token');
        const res = await fetch(`/api/folders/${folderId}/meetings`, {
            method: 'PUT',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(ids)
        });

        if (res.ok) {
            // Success
            selectedMeetingIds.clear();
            updateBulkUI();
            loadMeetings(); // Reload to refresh list
        } else {
            alert("이동 실패");
        }
    } catch (e) {
        console.error(e);
        alert("오류 발생");
    }
}

async function deleteSelectedMeetings() {
    if (selectedMeetingIds.size === 0) return;

    const ids = Array.from(selectedMeetingIds);
    if (!confirm(`선택한 ${ids.length}개의 회의를 삭제하시겠습니까?`)) return;

    try {
        const token = localStorage.getItem('access_token');
        const res = await fetch('/api/meeting/', {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(ids)
        });

        if (res.ok) {
            selectedMeetingIds.clear();
            updateBulkUI();
            loadMeetings();
        } else {
            alert("삭제 실패");
        }
    } catch (e) {
        console.error(e);
        alert("오류 발생");
    }
}

// meeting.py에서 loadMeetings 수정 필요: 전역 변수 allMeetings에 저장
async function loadMeetings() {
    const list = document.getElementById('meeting-list');
    list.innerHTML = '<div class="loading-state"><i class="fa-solid fa-circle-notch fa-spin"></i><p>불러오는 중...</p></div>';

    try {
        const token = localStorage.getItem('access_token');
        if (!token) return;

        const res = await fetch('/api/meeting/', {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (res.ok) {
            allMeetings = await res.json();
            selectedMeetingIds.clear(); // List reloaded, clear selection
            updateBulkUI();
            renderMeetingList(allMeetings);
        } else if (res.status === 401 || res.status === 403) {
            window.location.href = '/login';
        } else {
            list.innerHTML = '<div class="empty-state"><p>회의 목록을 불러오지 못했습니다.</p></div>';
        }
    } catch (e) {
        console.error(e);
        list.innerHTML = '<div class="empty-state"><p>오류가 발생했습니다.</p></div>';
    }
}

// 상태 메시지 헬퍼 함수
function getStatusDisplay(status) {
    switch (status) {
        case 'recording':
        case 'processing':
            return { text: 'AI 분석 중 (파일 크기에 따라 소요시간이 다릅니다.)', class: 'status-processing', icon: 'fa-spinner fa-spin' };
        case 'completed':
            return { text: '분석 완료', class: 'status-completed', icon: 'fa-check' };
        case 'error':
            return { text: '오류', class: 'status-error', icon: 'fa-circle-exclamation' };
        default:
            return { text: '대기 중', class: 'status-unknown', icon: 'fa-clock' };
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

    // processing 상태인 회의가 있는지 확인 (Set 업데이트)
    activeProcessingIds.clear();
    filtered.forEach(m => {
        if (m.status === 'processing' || m.status === 'recording') {
            activeProcessingIds.add(m.id);
        }
    });

    const hasProcessing = activeProcessingIds.size > 0;

    // 자동 새로고침 설정 (기존 타이머 제거)
    if (window.autoRefreshTimer) {
        clearTimeout(window.autoRefreshTimer);
        window.autoRefreshTimer = null;
    }

    // processing 상태가 있으면 5초 후 목록 새로고침 (상태 변경 확인용)
    if (hasProcessing) {
        window.autoRefreshTimer = setTimeout(() => {
            // console.log('Auto-refreshing meetings...');
            loadMeetings();
        }, 5000);

        // [New] 1초마다 진행률 갱신 (애니메이션 효과)
        if (window.progressInterval) clearInterval(window.progressInterval);
        window.progressInterval = setInterval(updateProgressBars, 1000);
    } else {
        // 처리 중인 항목 없으면 타이머 해제
        if (window.progressInterval) {
            clearInterval(window.progressInterval);
            window.progressInterval = null;
        }
    }

    let finalHtml = filtered.map(meeting => {
        const isSelected = selectedMeetingIds.has(meeting.id);

        const date = new Date(meeting.created_at).toLocaleString();
        const statusInfo = getStatusDisplay(meeting.status);

        const title = meeting.title || '제목 없는 회의';
        let fontSize = '1.2rem';
        if (title.length > 30) fontSize = '0.9rem';
        else if (title.length > 20) fontSize = '1.0rem';
        else if (title.length > 12) fontSize = '1.1rem';

        // 진행률 바 (processing 상태일 때만 표시)
        let progressBarHtml = '';
        if (meeting.status === 'processing' || meeting.status === 'recording') {
            progressBarHtml = `
                <div class="progress-wrapper" style="margin-top:8px; width: 100%;">
                    <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
                        <span style="font-size:0.75rem; color:#94a3b8;">분석 진행률</span>
                        <span id="progress-text-${meeting.id}" style="font-size:0.75rem; color:#3b82f6; font-weight:bold;">0%</span>
                    </div>
                    <div class="progress-bar-bg" style="background:#334155; height:4px; border-radius:2px; overflow:hidden;">
                        <div id="progress-bar-${meeting.id}" style="width:0%; height:100%; background:#3b82f6; transition:width 0.3s ease;"></div>
                    </div>
                </div>
            `;
        }

        return `
        <div class="meeting-card ${isSelected ? 'selected' : ''}" 
             draggable="true" 
             ondragstart="drag(event, ${meeting.id})"
             onclick="toggleSelection(event, ${meeting.id})"
             style="cursor: pointer; position: relative;">
            
            <div class="card-selection-indicator" style="position: absolute; top: 10px; left: 10px; z-index: 10;">
                <i class="fa-solid fa-circle-check" id="check-meeting-${meeting.id}" 
                   style="color: ${isSelected ? '#3b82f6' : '#94a3b8'}; font-size: 1.2rem; transition: color 0.2s;"></i>
            </div>

            <button class="btn-delete" onclick="deleteMeeting(event, ${meeting.id})" style="position: absolute; top: 10px; right: 10px; z-index: 10;">
                <i class="fa-solid fa-trash"></i>
            </button>
            <div style="margin-left: 30px; margin-top: 5px;" onclick="if(!event.target.closest('.card-selection-indicator')) location.href='/meeting/${meeting.id}'; event.stopPropagation();">
                <div class="meeting-title" id="title-container-${meeting.id}" style="display:flex; align-items:center; gap:8px; min-height: 30px;">
                     <span id="title-text-${meeting.id}" style="font-size: ${fontSize}">${title}</span>
                     <button class="btn-edit" id="btn-edit-${meeting.id}" onclick="enableEditMode(event, ${meeting.id})" title="이름 변경" style="background:none; border:none; cursor: pointer; color: #888; font-size: 0.9rem;">
                        <i class="fa-solid fa-pen"></i>
                    </button>
                </div>
                <div class="meeting-date"><i class="fa-regular fa-clock"></i> ${date}</div>
                <span class="meeting-status ${statusInfo.class}">
                    <i class="fa-solid ${statusInfo.icon}"></i> ${statusInfo.text}
                </span>
                ${meeting.status === 'error' ? `
                    <button class="btn btn-sm" onclick="retryAnalysis(event, ${meeting.id})" 
                            style="margin-top: 8px; padding: 6px 12px; font-size: 0.85rem;">
                        <i class="fa-solid fa-rotate-right"></i> 재분석
                    </button>
                ` : ''}
                ${(meeting.status === 'completed' || meeting.status === 'recording') && meeting.description === '실시간 녹음' ? `
                    <button class="btn btn-sm btn-outline" onclick="event.stopPropagation(); location.href='/recording?resume=${meeting.id}'" 
                            style="margin-top: 8px; padding: 6px 12px; font-size: 0.85rem; border-color: #3b82f6; color: #3b82f6;">
                        <i class="fa-solid fa-microphone-lines"></i> 이어서 녹음
                    </button>
                ` : ''}
                ${progressBarHtml}
            </div>
        </div>
    `}).join('');

    // 만약 업로드 중이라면 임시 카드 추가
    if (window.uploadingFileState) {
        const u = window.uploadingFileState;
        const tempCard = `
        <div class="meeting-card selected" style="border: 2px solid #3b82f6; background-color: rgba(59, 130, 246, 0.05);">
            <div style="position: absolute; top: 10px; right: 10px; z-index: 10;">
                <i class="fa-solid fa-cloud-arrow-up" style="color:#3b82f6"></i>
            </div>
            <div style="margin-left: 30px; margin-top: 5px;">
                <div class="meeting-title" style="display:flex; align-items:center; gap:8px;">
                     <span style="font-size: 1.1rem; font-weight:bold;">${u.title}</span>
                </div>
                <div class="meeting-date"><i class="fa-regular fa-clock"></i> ${new Date().toLocaleString()}</div>
                <span class="meeting-status status-processing">
                    <i class="fa-solid fa-upload"></i> 업로드 중...
                </span>
                
                <div class="progress-wrapper" style="margin-top:8px; width: 100%;">
                    <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
                        <span style="font-size:0.75rem; color:#94a3b8;">${u.filename}</span>
                        <span id="upload-progress-text" style="font-size:0.75rem; color:#3b82f6; font-weight:bold;">${u.percent}%</span>
                    </div>
                    <div class="progress-bar-bg" style="background:#334155; height:4px; border-radius:2px; overflow:hidden;">
                        <div id="upload-progress-bar" style="width:${u.percent}%; height:100%; background:#3b82f6; transition:width 0.1s linear;"></div>
                    </div>
                </div>
            </div>
        </div>`;

        // 리스트 최상단에 추가
        finalHtml = tempCard + finalHtml;
    }

    list.innerHTML = finalHtml;
}

async function updateProgressBars() {
    if (activeProcessingIds.size === 0) return;

    const token = localStorage.getItem('access_token');

    // 비동기 병렬 처리
    const updates = Array.from(activeProcessingIds).map(async (id) => {
        try {
            const bar = document.getElementById(`progress-bar-${id}`);
            const text = document.getElementById(`progress-text-${id}`);

            // DOM에 요소가 없으면 (화면이 바뀌었거나 스크롤 등) 패스
            if (!bar || !text) return;

            const res = await fetch(`/api/progress/${id}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (res.ok) {
                const data = await res.json();
                const percent = data.progress || 0;

                if (percent === 100) {
                    bar.style.width = '100%';
                    text.innerText = '100%';

                    // [New] 100% 도달 시 0.5초 대기 후 목록 새로고침
                    if (!window.finishedMeetingIds) window.finishedMeetingIds = new Set();
                    if (!window.finishedMeetingIds.has(id)) {
                        window.finishedMeetingIds.add(id);
                        setTimeout(() => {
                            loadMeetings(); // 완료 상태 반영을 위해 새로고침
                            window.finishedMeetingIds.delete(id);
                        }, 500);
                    }
                } else {
                    bar.style.width = `${percent}%`;
                    text.innerText = `${percent}%`;
                }
            }
        } catch (e) {
            console.error(`Progress fetch failed for ${id}`, e);
        }
    });

    await Promise.all(updates);
}

// Drag and Drop
function allowDrop(ev) {
    ev.preventDefault();
}

function drag(ev, meetingId) {
    // If dragging an unselected item, select it exclusively
    if (!selectedMeetingIds.has(meetingId)) {
        // Clear previous visual selection
        selectedMeetingIds.forEach(id => {
            const cb = document.getElementById(`check-meeting-${id}`);
            if (cb) cb.style.color = '#94a3b8';
        });

        selectedMeetingIds.clear();
        selectedMeetingIds.add(meetingId);

        // Update visual for dragged item
        const cb = document.getElementById(`check-meeting-${meetingId}`);
        if (cb) cb.style.color = '#3b82f6';

        updateBulkUI();
    }

    // Pass list of IDs
    const ids = Array.from(selectedMeetingIds);
    ev.dataTransfer.setData("meetingIds", JSON.stringify(ids));
}

async function drop(ev, folderId) {
    ev.preventDefault();
    const idsData = ev.dataTransfer.getData("meetingIds");
    if (!idsData) return;

    const ids = JSON.parse(idsData);

    // 폴더 이름 찾기
    const targetFolder = allFolders.find(f => f.id === folderId);
    const targetFolderName = targetFolder ? targetFolder.name : "미분류";

    if (!confirm(`${ids.length}개의 회의를 '${targetFolderName}'(으)로 이동하시겠습니까?`)) {
        return;
    }

    // API Call to move meetings (Bulk)
    const token = localStorage.getItem('access_token');

    try {
        const res = await fetch(`/api/folders/${folderId}/meetings`, {
            method: 'PUT',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(ids)
        });

        if (res.ok) {
            // Update local data
            ids.forEach(id => {
                const m = allMeetings.find(m => m.id == id);
                if (m) m.folder_id = folderId;
            });

            selectedMeetingIds.clear();
            updateBulkUI();
            renderMeetingList(allMeetings); // Refresh view
        } else {
            alert("이동 실패");
        }
    } catch (e) {
        console.error(e);
        alert("이동 중 오류가 발생했습니다.");
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

            // 파일 저장 후 메타데이터 모달 표시
            selectedFile = file;
            showMetadataModal('upload');
        });
    }
}

/**
 * 메타데이터 모달 표시 (dashboard용)
 */
function showMetadataModal(mode = 'upload') {
    const modal = document.getElementById('metadata-modal');
    const dateInput = document.getElementById('meeting-date-input');

    // 파일 업로드인 경우 직접 입력 가능
    if (mode === 'upload') {
        dateInput.removeAttribute('readonly');
        dateInput.style.backgroundColor = '';
        dateInput.style.cursor = '';
        dateInput.value = ''; // 초기화

        // 버튼 이벤트 연결
        const submitBtn = document.getElementById('metadata-submit-btn');
        if (submitBtn) {
            submitBtn.textContent = "확인";
            submitBtn.onclick = submitMetadata;
        }
    }

    modal.style.display = 'flex';
}

/**
 * 메타데이터 모달 닫기 (dashboard용)
 */
function closeMetadataModal() {
    const modal = document.getElementById('metadata-modal');
    const form = document.getElementById('metadata-form');
    const fileInput = document.getElementById('file-input');

    form.reset();
    modal.style.display = 'none';

    // 파일 선택 취소
    if (fileInput) fileInput.value = '';
}

/**
 * 메타데이터 제출 (dashboard용 - 파일 업로드)
 */
async function submitMetadata() {
    const form = document.getElementById('metadata-form');

    // 유효성 검사
    if (!form.checkValidity()) {
        alert('모든 필드를 입력해주세요.');
        return;
    }

    // 메타데이터 수집
    const metadata = {
        title: document.getElementById('meeting-title-input').value.trim(),
        meeting_type: document.getElementById('meeting-type-input').value.trim(),
        meeting_date: document.getElementById('meeting-date-input').value,
        attendees: document.getElementById('meeting-attendees-input').value.trim(),
        writer: document.getElementById('meeting-writer-input').value.trim()
    };

    // 모달 닫기
    closeMetadataModal();

    // 파일 업로드 진행
    await uploadFileWithMetadata(metadata);
}

/**
 * 메타데이터와 함께 파일 업로드
 */
/**
 * 메타데이터와 함께 파일 업로드 (XHR with Progress)
 */
async function uploadFileWithMetadata(metadata) {
    // 전역 변수에 저장된 파일 사용
    const file = selectedFile;

    if (!file) {
        alert('파일이 선택되지 않았습니다.');
        return;
    }

    const token = localStorage.getItem('access_token');
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', metadata.title);
    formData.append('meeting_type', metadata.meeting_type);
    formData.append('meeting_date', metadata.meeting_date);
    formData.append('attendees', metadata.attendees);
    formData.append('writer', metadata.writer);

    // [전역 상태 설정] 업로드 중 상태 시작
    window.uploadingFileState = {
        title: metadata.title,
        filename: file.name,
        percent: 0
    };

    // UI 즉시 갱신 (임시 카드 표시)
    renderMeetingList(allMeetings);

    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/api/upload/file', true);
        xhr.setRequestHeader('Authorization', `Bearer ${token}`);

        // Upload Progress
        xhr.upload.onprogress = function (e) {
            if (e.lengthComputable) {
                const percentComplete = (e.loaded / e.total) * 100;

                // 전역 상태 업데이트
                if (window.uploadingFileState) {
                    window.uploadingFileState.percent = Math.round(percentComplete);

                    // DOM바만 직접 조작 (전체 렌더링은 비효율적이므로)
                    const bar = document.getElementById('upload-progress-bar');
                    const text = document.getElementById('upload-progress-text');
                    if (bar && text) {
                        bar.style.width = window.uploadingFileState.percent + '%';
                        text.innerText = window.uploadingFileState.percent + '%';
                    }
                }
            }
        };

        // Completion
        xhr.onload = async function () {
            // 업로드 상태 해제
            window.uploadingFileState = null;

            if (xhr.status >= 200 && xhr.status < 300) {
                // 성공 시 목록 갱신 (임시 카드는 사라지고 실제 카드가 'processing' 상태로 등장)
                await loadMeetings();

                // Reset inputs
                const fileInput = document.getElementById('file-input');
                if (fileInput) fileInput.value = '';
                selectedFile = null;
                resolve();
            } else {
                let errorMessage = '업로드 실패';
                try {
                    const response = JSON.parse(xhr.responseText);
                    errorMessage = response.detail || errorMessage;
                } catch (e) { console.error(e); }

                alert('실패: ' + errorMessage);
                // 실패했으니 임시 카드 제거를 위해 다시 렌더링
                renderMeetingList(allMeetings);
                resolve();
            }
        };

        // Error
        xhr.onerror = function () {
            window.uploadingFileState = null;
            renderMeetingList(allMeetings);

            alert('네트워크 오류로 업로드에 실패했습니다.');
            console.error('Upload network error');
            resolve();
        };

        xhr.send(formData);
    });
}



function enableEditMode(event, meetingId) {
    event.stopPropagation();
    const container = document.getElementById(`title-container-${meetingId}`);
    const textSpan = document.getElementById(`title-text-${meetingId}`);
    const editBtn = document.getElementById(`btn-edit-${meetingId}`);

    if (!container || !textSpan || !editBtn) return;

    // 카드 드래그 비활성화
    const card = container.closest('.meeting-card');
    if (card) card.setAttribute('draggable', 'false');

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

    // 카드 드래그 활성화 복구
    const card = container.closest('.meeting-card');
    if (card) card.setAttribute('draggable', 'true');
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

    if (!confirm("이 회의를 삭제하시겠습니까?")) {
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

// 재분석 함수 (오류 발생 시 재시도)
async function retryAnalysis(event, meetingId) {
    event.stopPropagation(); // 카드 클릭 이벤트 방지

    if (!confirm("이 회의를 다시 분석하시겠습니까?\n(기존 전사 데이터는 유지되며, STT 및 요약만 재실행됩니다)")) {
        return;
    }

    try {
        const token = localStorage.getItem('access_token');

        // 상태를 processing으로 변경하고 백그라운드 작업 재시작
        const response = await fetch(`/api/meeting/${meetingId}/retry`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (response.ok) {
            alert('재분석이 시작되었습니다. 잠시 후 결과를 확인해주세요.');
            await loadMeetings(); // 목록 갱신
        } else {
            const error = await response.json();
            alert('재분석 실패: ' + (error.detail || '알 수 없는 오류'));
        }
    } catch (err) {
        console.error(err);
        alert('재분석 중 오류가 발생했습니다.');
    }
}
