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
            }
            // 윈도우 경로 역슬래시 처리
            relativePath = relativePath.replace(/\\/g, '/');
            if (relativePath.startsWith('/')) relativePath = relativePath.substring(1);

            const player = document.getElementById('audio-player');
            if (player) {
                player.src = `/media/${relativePath}`;

                // 초기 Duration 표시 (DB 값 우선)
                const durationElem = document.getElementById('meeting-duration');
                const playerDurationElem = document.getElementById('player-total-duration');

                const setDurationText = (seconds) => {
                    const text = `총 재생 시간: ${formatDuration(seconds)}`;
                    if (durationElem) durationElem.innerText = text;
                    if (playerDurationElem) playerDurationElem.innerText = text;
                };

                if (meeting.duration) {
                    setDurationText(meeting.duration);
                } else {
                    if (durationElem) durationElem.innerText = `총 재생 시간: --:--`;
                }

                // 디버깅용 이벤트 리스너
                player.addEventListener('error', (e) => {
                    console.error("Audio Load Error:", player.error);
                });

                player.addEventListener('loadedmetadata', () => {
                    console.log("Audio Metadata Loaded. Duration:", player.duration);
                    if (player.duration && player.duration !== Infinity && !isNaN(player.duration)) {
                        setDurationText(player.duration);
                    } else if (meeting.duration) {
                        // 메타데이터가 없는 경우 DB 값 유지
                        setDurationText(meeting.duration);
                    }
                });

                // 타임 업데이트 리스너 추가 (싱크 하이라이팅)
                player.addEventListener('timeupdate', () => {
                    highlightCurrentTranscript(player.currentTime);
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
                    item.dataset.startTime = t.start_time; // 시작 시간 저장
                    item.dataset.endTime = t.end_time; // 종료 시간 저장
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

        // 중간 요약 타임라인 로딩 로직
        const timelineSection = document.getElementById('summary-timeline-section');
        const timelineContent = document.getElementById('summary-timeline-content');

        if (meeting.intermediate_summaries && meeting.intermediate_summaries.length > 0) {
            if (timelineSection) timelineSection.style.display = 'block';
            if (timelineContent) {
                timelineContent.innerHTML = ''; // 초기화

                // 생성 역순(최신순)으로 정렬하여 표시
                const sortedSummaries = [...meeting.intermediate_summaries].sort((a, b) =>
                    new Date(b.created_at) - new Date(a.created_at)
                );

                sortedSummaries.forEach(is => {
                    const timeStr = new Date(is.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                    const card = document.createElement('div');
                    card.className = 'summary-card';
                    card.style.marginBottom = '15px';
                    card.style.padding = '15px';
                    card.style.background = 'var(--bg-dark)';
                    card.style.borderRadius = '8px';
                    card.style.border = '1px solid var(--border)';

                    card.innerHTML = `
                        <div class="summary-time" style="font-size: 0.85rem; color: #3b82f6; font-weight: bold; margin-bottom: 5px;">
                            <i class="fa-regular fa-clock"></i> ${timeStr}
                        </div>
                        <div class="summary-text" style="font-size: 0.95rem; line-height: 1.6;">
                            ${is.content}
                        </div>
                    `;
                    timelineContent.appendChild(card);
                });
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
    if (!confirm('AI 회의록 생성을 시작하시겠습니까?\n(기존 요약이 있다면 덮어씌워집니다)')) return;

    const btn = document.getElementById('btn-summary');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> 요청 중...';
    }

    try {
        const response = await fetch(`/api/meeting/${meetingId}/summarize`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (response.ok) {
            alert('요약 생성이 시작되었습니다.\n완료되면 화면이 자동으로 새로고침됩니다.');
            // 3초 후 새로고침 (간단한 UX)
            // 더 정교하게 하려면 폴링을 해야 하지만, 일단 요청 -> 대기 -> 완료 흐름이므로
            // 사용자가 기다리면 됨. 혹은 dashboard 처럼 polling?
            // 여기서는 일단 button을 "분석 중..."으로 바꾸고 
            // 5초마다 상태를 체크하는 로직을 추가하는 것이 좋음.

            if (btn) btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 분석 중...';

            // Polling check
            const checkInterval = setInterval(async () => {
                const res = await fetch(`/api/meeting/${meetingId}`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                if (res.ok) {
                    const data = await res.json();
                    if (data.status === 'completed') {
                        clearInterval(checkInterval);
                        window.location.reload();
                    }
                }
            }, 3000);

        } else {
            alert('요청 실패');
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> 회의록 생성';
            }
        }
    } catch (err) {
        console.error(err);
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> 회의록 생성';
        }
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


// 현재 재생 위치에 맞는 전사 하이라이트
function highlightCurrentTranscript(currentTime) {
    const items = document.querySelectorAll('.transcript-item');
    items.forEach(item => {
        const start = parseFloat(item.dataset.startTime);
        const end = parseFloat(item.dataset.endTime) || (start + 5); // end가 없으면 대략 5초로 가정

        if (currentTime >= start && currentTime < end) {
            // 현재 활성화된 아이템 찾기
            const currentActive = document.querySelector('.transcript-item.active-transcript');

            // 이미 활성화된 아이템이 지금 아이템과 같으면 스킵 (불필요한 DOM 조작 방지)
            if (currentActive === item) return;

            // 다른 활성화된 아이템 끄기
            if (currentActive) {
                currentActive.classList.remove('active-transcript');
            }

            // 현재 아이템 활성화
            item.classList.add('active-transcript');

            // 스크롤 이동 (부드럽게, 중앙 정렬)
            item.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    });
}

// 스타일 추가
const style = document.createElement('style');
style.textContent = `
    .transcript-item.active-transcript {
        background-color: rgba(59, 130, 246, 0.1);
        border-left: 3px solid #3b82f6;
        padding-left: 12px; /* 기존 패딩 + 보더 공간 */
    }
    .transcript-item {
        transition: all 0.2s ease;
        padding: 5px;
        border-radius: 4px;
    }
`;
document.head.appendChild(style);

// 시간 포맷팅 (초 -> HH:MM:SS)
function formatDuration(seconds) {
    if (!seconds || isNaN(seconds)) return "00:00";

    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);

    if (h > 0) {
        return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    } else {
        return `${m}:${s.toString().padStart(2, '0')}`;
    }
}

window.exportMeeting = exportMeeting;
window.closeMetadataModal = closeMetadataModal;
window.submitMetadataAndExport = submitMetadataAndExport;
window.seekAudio = seekAudio;
window.formatDuration = formatDuration;
