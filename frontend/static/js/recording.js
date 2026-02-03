/**
 * 실시간 녹음 및 STT JavaScript
 * 
 * MediaRecorder API + WebSocket을 사용한 실시간 음성 인식
 */

// 전역 변수
let websocket = null;
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;
let recordingSeconds = 0;
let fullTranscript = "";
let currentMeetingId = null; // 현재 녹음 중인 회의 ID

// DOM 요소
const statusDot = document.querySelector('.status-dot');
const statusText = document.querySelector('.status-text');
const btnStart = document.getElementById('btn-start');
const btnStop = document.getElementById('btn-stop');
const timerDisplay = document.getElementById('timer-display');
const recordingTimerEl = document.getElementById('recording-timer');
const bufferStatus = document.getElementById('buffer-status');
const bufferProgress = document.getElementById('buffer-progress');
const bufferText = document.getElementById('buffer-text');
const transcriptContent = document.getElementById('transcript-content');
const fullTranscriptSection = document.getElementById('full-transcript-section');
const fullTranscriptEl = document.getElementById('full-transcript');

/**
 * WebSocket 연결
 */
function connectWebSocket() {
    const token = localStorage.getItem('access_token');
    if (!token) {
        alert('로그인이 필요합니다.');
        window.location.href = '/login';
        return;
    }

    const clientId = 'client_' + Date.now();
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/api/recording/ws/${clientId}?token=${token}`;

    websocket = new WebSocket(wsUrl);

    websocket.onopen = function () {
        console.log('WebSocket 연결됨');
        updateStatus('connected', '연결됨');
    };

    websocket.onmessage = function (event) {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };

    websocket.onclose = function () {
        console.log('WebSocket 연결 끊김');
        updateStatus('disconnected', '연결 끊김');
        stopRecording();
    };

    websocket.onerror = function (error) {
        console.error('WebSocket 에러:', error);
        updateStatus('disconnected', '연결 오류');
    };
}

/**
 * WebSocket 메시지 처리
 */
function handleWebSocketMessage(data) {
    switch (data.type) {
        case 'connected':
            console.log('서버 연결 확인:', data.message);
            break;

        case 'buffering':
            // 버퍼링 상태 업데이트
            const progress = (data.buffer_seconds / 5) * 100;
            bufferProgress.style.width = progress + '%';
            bufferText.textContent = `버퍼링: ${data.buffer_seconds.toFixed(1)}/5초`;
            break;

        case 'transcript':
            // 전사 결과 수신
            appendTranscript(data.text);
            // 버퍼 초기화
            bufferProgress.style.width = '0%';
            bufferText.textContent = '버퍼링: 0/5초';
            break;

        case 'intermediate_summary':
            // 중간 요약 수신
            appendIntermediateSummary(data.content);
            break;

        case 'error':
            console.error('서버 에러:', data.message);
            break;

        case 'meeting_created':
            currentMeetingId = data.meeting_id;
            console.log('회의 생성됨 ID:', currentMeetingId);
            break;
    }
}

/**
 * 상태 업데이트
 */
function updateStatus(status, text) {
    statusDot.className = 'status-dot ' + status;
    statusText.textContent = text;
}

/**
 * 녹음 시작 버튼 클릭 - 메타데이터 모달 표시
 */
let meetingMetadata = null;

function startRecording() {
    // 메타데이터 입력 없이 바로 녹음 시작 (기본값 사용)
    startRecordingImmediate();
}


/**
 * 즉시 녹음 시작 (기본 메타데이터 사용)
 */
function startRecordingImmediate() {
    // 즉시 녹음 시작 (기본 메타데이터 사용)
    currentMeetingId = null; // 초기화

    const now = new Date();

    // 기본 메타데이터 생성
    // YYYY-MM-DDTHH:mm 형식
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const formattedDate = `${year}-${month}-${day}T${hours}:${minutes}`;

    // 기본 메타데이터 생성
    meetingMetadata = {
        title: `실시간 회의 ${year}-${month}-${day} ${hours}:${minutes}`,
        meeting_type: "실시간 녹음",
        meeting_date: formattedDate,
        attendees: "",
        writer: ""
    };

    startRecordingWithMetadata();
}

/**
 * 메타데이터 모달 표시
 */
function showMetadataModal(mode = 'recording') {
    const modal = document.getElementById('metadata-modal');
    const dateInput = document.getElementById('meeting-date-input');

    // 실시간 녹음인 경우 현재 시간으로 자동 설정 (readonly)
    if (mode === 'recording') {
        const now = new Date();
        // datetime-local 형식으로 변환 (YYYY-MM-DDTHH:mm)
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, '0');
        const day = String(now.getDate()).padStart(2, '0');
        const hours = String(now.getHours()).padStart(2, '0');
        const minutes = String(now.getMinutes()).padStart(2, '0');
        const formattedDate = `${year}-${month}-${day}T${hours}:${minutes}`;

        dateInput.value = formattedDate;
        dateInput.setAttribute('readonly', 'readonly');
        dateInput.style.backgroundColor = 'var(--bg-dark)';
        dateInput.style.cursor = 'not-allowed';
    } else {
        // 파일 업로드인 경우 직접 입력 가능
        dateInput.removeAttribute('readonly');
        dateInput.style.backgroundColor = '';
        dateInput.style.cursor = '';
    }

    // 버튼 이벤트 연결
    const submitBtn = document.getElementById('metadata-submit-btn');
    if (submitBtn) {
        submitBtn.textContent = "확인";
        submitBtn.onclick = submitMetadata;
    }

    modal.style.display = 'flex';
}

/**
 * 메타데이터 모달 닫기
 */
function closeMetadataModal() {
    const modal = document.getElementById('metadata-modal');
    const form = document.getElementById('metadata-form');
    form.reset();
    modal.style.display = 'none';
}

/**
 * 메타데이터 제출
 */
function submitMetadata() {
    const form = document.getElementById('metadata-form');

    // 유효성 검사
    if (!form.checkValidity()) {
        alert('모든 필드를 입력해주세요.');
        return;
    }

    // 메타데이터 수집
    meetingMetadata = {
        title: document.getElementById('meeting-title-input').value.trim(),
        meeting_type: document.getElementById('meeting-type-input').value.trim(),
        meeting_date: document.getElementById('meeting-date-input').value,
        attendees: document.getElementById('meeting-attendees-input').value.trim(),
        writer: document.getElementById('meeting-writer-input').value.trim(),
        status: 'completed', // 녹음 완료 상태로 명시
        duration: recordingSeconds // 녹음 시간 전송
    };

    // 모달 닫기
    closeMetadataModal();

    // 편집 모드인 경우 저장 후 대시보드로 이동
    if (window.isEditMode) {
        if (!currentMeetingId) {
            alert('회의 ID를 찾을 수 없어 저장에 실패했습니다.');
            window.location.href = '/';
            return;
        }

        const token = localStorage.getItem('access_token');
        fetch(`/api/meeting/${currentMeetingId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(meetingMetadata)
        })
            .then(response => {
                if (response.ok) {
                    alert('회의 정보가 업데이트되었습니다.');
                    window.location.href = '/';
                    window.isEditMode = false;
                } else {
                    alert('회의 정보 업데이트 실패');
                    console.error('Update failed:', response);
                }
            })
            .catch(err => {
                console.error('Network error:', err);
                alert('저장 중 오류가 발생했습니다.');
            });
    } else {
        // 실제 녹음 시작
        startRecordingWithMetadata();
    }
}

/**
 * 메타데이터와 함께 실제 녹음 시작
 */
/**
 * WebSocket 연결 대기 (Promise wrapper)
 */
function waitForConnection(ws, timeout = 10000) {
    return new Promise((resolve, reject) => {
        if (!ws) return reject(new Error("WebSocket is not initialized"));

        if (ws.readyState === WebSocket.OPEN) {
            return resolve();
        }

        const timer = setTimeout(() => {
            reject(new Error("WebSocket connection timeout"));
        }, timeout);

        const onOpen = () => {
            clearTimeout(timer);
            ws.removeEventListener('open', onOpen);
            resolve();
        };

        ws.addEventListener('open', onOpen);
    });
}

/**
 * 메타데이터와 함께 실제 녹음 시작
 */
async function startRecordingWithMetadata() {
    try {
        // 마이크 권한 요청
        const stream = await navigator.mediaDevices.getUserMedia({
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
                sampleRate: 16000
            }
        });

        // WebSocket 연결 확인 및 재연결
        if (!websocket || websocket.readyState !== WebSocket.OPEN) {
            console.log("WebSocket 연결 시도...");
            connectWebSocket();
        }

        // 연결 대기 (최대 10초)
        await waitForConnection(websocket);

        console.log("WebSocket 연결 확인 완료, 메타데이터 전송 시도");

        // 메타데이터 전송 (필수)
        if (meetingMetadata) {
            websocket.send(JSON.stringify({
                type: 'metadata',
                data: meetingMetadata
            }));
            console.log('메타데이터 전송:', meetingMetadata);
        } else {
            throw new Error("메타데이터가 없습니다.");
        }

        // START! MediaRecorder 설정
        const options = { mimeType: 'audio/webm;codecs=opus' };
        mediaRecorder = new MediaRecorder(stream, options);

        mediaRecorder.ondataavailable = function (event) {
            if (event.data.size > 0 && websocket && websocket.readyState === WebSocket.OPEN) {
                // 오디오 청크를 WebSocket으로 전송
                websocket.send(event.data);
            }
        };

        mediaRecorder.onstop = function () {
            stream.getTracks().forEach(track => track.stop());
        };

        // 500ms마다 오디오 청크 생성
        mediaRecorder.start(500);
        isRecording = true;

        // UI 업데이트
        btnStart.disabled = true;
        btnStop.disabled = false;
        recordingTimerEl.style.display = 'flex';
        bufferStatus.style.display = 'block';
        transcriptContent.innerHTML = '';
        updateStatus('recording', '녹음 중...');

        // 타이머 시작
        recordingSeconds = 0;
        recordingTimer = setInterval(updateTimer, 1000);

    } catch (error) {
        console.error('녹음 시작 실패:', error);
        alert(`녹음 시작 실패: ${error.message}`);

        // 실패 시 정리
        if (websocket) {
            // websocket.close(); // 연결은 유지?
        }
        isRecording = false;
        btnStart.disabled = false;
    }
}

/**
 * 녹음 중지
 */
function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
    }

    isRecording = false;

    // WebSocket 연결 종료 (이것이 서버의 요약 로직을 트리거함)
    if (websocket) {
        websocket.close();
    }

    // UI 업데이트
    btnStart.disabled = false;
    btnStop.disabled = true;
    recordingTimerEl.style.display = 'none';
    bufferStatus.style.display = 'none';
    updateStatus('connected', '녹음 완료');

    // 타이머 정지
    if (recordingTimer) {
        clearInterval(recordingTimer);
        recordingTimer = null;
    }

    // 전체 전사 결과 표시
    if (fullTranscript.trim()) {
        fullTranscriptSection.style.display = 'block';
        fullTranscriptEl.value = fullTranscript;
    }

    // 메타데이터 수정 확인 모달 표시
    showEditConfirmationModal();
}

/**
 * 메타데이터 수정 확인 모달 표시
 */
function showEditConfirmationModal() {
    // 사용자 요청: 녹음 종료 후 무조건 수정 모달 표시
    showEditMetadataModal();
}

/**
 * 메타데이터 편집 모달 표시
 */
function showEditMetadataModal() {
    const modal = document.getElementById('metadata-modal');
    const form = document.getElementById('metadata-form');

    // 기존 메타데이터로 폼 채우기
    if (meetingMetadata) {
        document.getElementById('meeting-title-input').value = meetingMetadata.title;
        document.getElementById('meeting-type-input').value = meetingMetadata.meeting_type;
        document.getElementById('meeting-date-input').value = meetingMetadata.meeting_date;
        document.getElementById('meeting-attendees-input').value = meetingMetadata.attendees;
        document.getElementById('meeting-writer-input').value = meetingMetadata.writer;
    }

    // 회의일시 필드를 편집 가능하게 변경
    const dateInput = document.getElementById('meeting-date-input');
    dateInput.removeAttribute('readonly');
    dateInput.style.backgroundColor = '';
    dateInput.style.cursor = '';

    modal.style.display = 'flex';

    // submitMetadata 함수를 재정의하여 편집 모드로 동작
    window.isEditMode = true;
}

/**
 * 타이머 업데이트
 */
function updateTimer() {
    recordingSeconds++;
    const minutes = Math.floor(recordingSeconds / 60);
    const seconds = recordingSeconds % 60;
    timerDisplay.textContent =
        String(minutes).padStart(2, '0') + ':' +
        String(seconds).padStart(2, '0');
}

/**
 * 전사 결과 추가
 */
function appendTranscript(text) {
    if (!text.trim()) return;

    // 기존 placeholder 제거
    const placeholder = transcriptContent.querySelector('.placeholder-text');
    if (placeholder) {
        placeholder.remove();
    }

    // 새 전사 결과 추가
    const span = document.createElement('span');
    span.className = 'transcript-segment';
    span.textContent = text + ' ';
    span.style.animation = 'fadeIn 0.3s';
    transcriptContent.appendChild(span);

    // 자동 스크롤
    transcriptContent.scrollTop = transcriptContent.scrollHeight;

    // 전체 전사에 추가
    fullTranscript += text + ' ';
}

/**
 * 전사 결과 복사
 */
function copyTranscript() {
    const text = transcriptContent.textContent;
    navigator.clipboard.writeText(text).then(() => {
        alert('복사되었습니다!');
    });
}

/**
 * 전사 결과 저장
 */
function saveTranscript() {
    // TODO: 서버에 저장하는 API 호출
    alert('저장 기능은 추후 구현 예정입니다.');
}

/**
 * 중간 요약 추가
 */
function appendIntermediateSummary(content) {
    const timelineSection = document.getElementById('summary-timeline-section');
    const timelineContent = document.getElementById('summary-timeline-content');

    // 섹션 표시
    timelineSection.style.display = 'block';

    // 현재 시간 (타임스탬프)
    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    // 카드 생성
    const card = document.createElement('div');
    card.className = 'summary-card';
    card.style.animation = 'slideIn 0.5s';

    card.innerHTML = `
        <div class="summary-time"><i class="fa-regular fa-clock"></i> ${timeStr}</div>
        <div class="summary-text">${content}</div>
    `;

    // 최신 요약이 위로 오도록 prepend
    timelineContent.prepend(card);
}

// 페이지 로드 시 WebSocket 연결
document.addEventListener('DOMContentLoaded', function () {
    // 로그인 확인
    const token = localStorage.getItem('access_token');
    if (!token) {
        window.location.href = '/login';
        return;
    }

    // WebSocket 연결
    connectWebSocket();

    // 메타데이터 제출 버튼 이벤트 연결 (즉시 시작 모드 대응)
    const submitBtn = document.getElementById('metadata-submit-btn');
    if (submitBtn) {
        submitBtn.onclick = submitMetadata;
    }
});

// 페이지 이탈 시 정리
window.addEventListener('beforeunload', function () {
    if (websocket) {
        websocket.close();
    }
    if (mediaRecorder && isRecording) {
        mediaRecorder.stop();
    }
});

// CSS 애니메이션 추가
const style = document.createElement('style');
style.textContent = `
    @keyframes fadeIn {
        from { opacity: 0; background: rgba(0, 200, 83, 0.2); }
        to { opacity: 1; background: transparent; }
    }
    .transcript-segment {
        padding: 2px 0;
    }

    @keyframes slideIn {
        from { opacity: 0; transform: translateY(-10px); }
        to { opacity: 1; transform: translateY(0); }
    }

    .summary-timeline-box {
        background: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 30px;
        border-left: 5px solid #3b82f6;
    }

    .timeline-container {
        display: flex;
        flex-direction: column;
        gap: 15px;
        max-height: 300px;
        overflow-y: auto;
        padding-right: 5px;
    }

    .summary-card {
        background: var(--bg-dark);
        border-radius: 8px;
        padding: 15px;
        border: 1px solid var(--border);
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }

    .summary-time {
        font-size: 0.85rem;
        color: #3b82f6;
        margin-bottom: 5px;
        font-weight: bold;
    }

    .summary-text {
        font-size: 0.95rem;
        line-height: 1.6;
        color: var(--text-primary);
    }
`;
document.head.appendChild(style);
