/**
 * 실시간 녹음 및 STT JavaScript
 * 
 * MediaRecorder API + WebSocket을 사용한 실시간 음성 인식
 */

// 전역 변수
let websocket = null;
let mediaRecorder = null;
let audioChunks = []; // 오디오 데이터 조각 수집용
let isRecording = false;
let currentMeetingId = null; // 현재 녹음 중인 회의 ID
let fullTranscript = ""; // 전체 전사 텍스트 저장용
let isIntentionalStop = false; // [Fix] 사용자가 직접 정지 버튼을 눌렀는지 여부
let isPaused = false; // [New] 일시정지 상태

// DOM 요소
const statusDot = document.querySelector('.status-dot');
const statusText = document.querySelector('.status-text');
const btnStart = document.getElementById('btn-start');
const btnStop = document.getElementById('btn-stop');
const btnPause = document.getElementById('btn-pause'); // [New]
const timerDisplay = document.getElementById('timer-display');
const recordingTimerEl = document.getElementById('recording-timer');
const bufferStatus = document.getElementById('buffer-status');
const bufferProgress = document.getElementById('buffer-progress');
const bufferText = document.getElementById('buffer-text');
const transcriptContent = document.getElementById('transcript-content');
const fullTranscriptSection = document.getElementById('full-transcript-section');
const fullTranscriptEl = document.getElementById('full-transcript');

// [New] 재연결 관련 변수
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_DELAY = 2000; // 2초

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

    // [Fix] 재연결 시 동일한 clientId를 사용하여 서버에서 세션을 식별할 수 있게 함 (필요 시)
    // 하지만 현재 서버는 매번 세션을 새로 생성하므로, 우선은 유지만 되도록 함.
    if (!window.currentClientId) {
        window.currentClientId = 'client_' + Date.now();
    }
    const clientId = window.currentClientId;
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/api/recording/ws/${clientId}?token=${token}`;

    console.log(`WebSocket 연결 시도 중... (시도 ${reconnectAttempts + 1}/${MAX_RECONNECT_ATTEMPTS})`);
    websocket = new WebSocket(wsUrl);

    websocket.onopen = function () {
        console.log('WebSocket 연결됨');
        reconnectAttempts = 0; // 성공 시 카운트 초기화
        updateStatus('connected', isRecording ? '재연결됨 (녹음 중)' : '연결됨');

        // [New] 만약 녹음 중에 재연결된 것이라면, 현재 진행 중인 메타데이터를 다시 보내서 세션을 복구 시도
        if (isRecording && meetingMetadata) {
            console.log('녹음 중 재연결됨. 메타데이터 재전송...');
            websocket.send(JSON.stringify({
                type: 'metadata',
                data: {
                    ...meetingMetadata,
                    reconnect: true, // 재연결임을 알림
                    meeting_id: currentMeetingId // 기존 ID 전달
                }
            }));
        }
    };

    websocket.onmessage = function (event) {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };

    websocket.onclose = function () {
        console.log('WebSocket 연결 끊김');

        // [Fix] 의도하지 않은 끊김이고 녹음 중인 경우 재연결 시도
        if (isRecording && !isIntentionalStop) {
            if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                reconnectAttempts++;
                updateStatus('disconnected', `연결 끊김, 재연결 시도 중... (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`);
                setTimeout(connectWebSocket, RECONNECT_DELAY);
            } else {
                updateStatus('disconnected', '재연결 실패');
                alert("서버와 연결이 완전히 끊겨 녹음을 중단합니다. 페이지를 새로고침 해주세요.");
                stopRecording();
            }
        } else {
            updateStatus('disconnected', '연결 종료');
        }
    };

    websocket.onerror = function (error) {
        console.error('WebSocket 에러:', error);
        // onerror 후 바로 onclose가 호출되므로 여기서 별도 처리는 생략
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
            appendTranscript(data.text, data.transcript_id);
            // 버퍼 초기화
            bufferProgress.style.width = '0%';
            bufferText.textContent = '버퍼링: 0/5초';
            break;

        case 'transcript_update':
            // [하이브리드 전략] LLM 교정 텍스트 수신
            updateTranscript(data.transcript_id, data.text);
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
    isIntentionalStop = false; // [Fix] 초기화
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
        title: `실시간 회의 ${year}. ${month}. ${day}. ${hours}:${minutes}`, // 더 보기 좋은 포맷으로 변경
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

    meetingMetadata = {
        title: document.getElementById('meeting-title-input').value.trim(),
        meeting_type: document.getElementById('meeting-type-input').value.trim(),
        meeting_date: document.getElementById('meeting-date-input').value,
        attendees: document.getElementById('meeting-attendees-input').value.trim(),
        writer: document.getElementById('meeting-writer-input').value.trim(),
        status: 'processing', // 분석 진행 중 상태로 설정 (요약 완료 후 백엔드에서 'completed'로 변경)
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
                // 1. WebSocket 전송 (실시간 STT용)
                websocket.send(event.data);

                // 2. 메모리에 수집 (종료 시 최종 업로드용)
                audioChunks.push(event.data);
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

        // [New] 일시정지 버튼 활성화
        btnPause.style.display = 'inline-block';
        btnPause.disabled = false;
        btnPause.innerHTML = '<i class="fa-solid fa-pause"></i> 일시정지';
        btnPause.className = 'btn btn-pause';
        isPaused = false;

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
 * [New] 일시정지 / 재개 토글
 */
function togglePause() {
    if (!mediaRecorder || mediaRecorder.state === 'inactive') return;

    if (!isPaused) {
        // 일시정지 (PAUSE)
        mediaRecorder.pause();
        isPaused = true;

        // UI 변경: 일시정지 -> 재개 버튼으로
        btnPause.innerHTML = '<i class="fa-solid fa-play"></i> 재개';
        btnPause.className = 'btn btn-resume';
        updateStatus('paused', '일시정지됨');

        // 타이머 정지
        if (recordingTimer) {
            clearInterval(recordingTimer);
            recordingTimer = null;
        }
    } else {
        // 재개 (RESUME)
        mediaRecorder.resume();
        isPaused = false;

        // UI 변경: 재개 -> 일시정지 버튼으로
        btnPause.innerHTML = '<i class="fa-solid fa-pause"></i> 일시정지';
        btnPause.className = 'btn btn-pause';
        updateStatus('recording', '녹음 중...');

        // 타이머 재개
        recordingTimer = setInterval(updateTimer, 1000);
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

    // [New] 일시정지 버튼 숨김
    btnPause.style.display = 'none';
    btnPause.disabled = true;

    recordingTimerEl.style.display = 'none';
    bufferStatus.style.display = 'none';
    updateStatus('connected', '녹음 완료');

    // 타이머 정지
    if (recordingTimer) {
        clearInterval(recordingTimer);
        recordingTimer = null;
    }

    // 전체 전사 결과 표시 (DOM에서 최신 상태로 재구성)
    fullTranscript = Array.from(document.querySelectorAll('.transcript-segment'))
        .map(span => span.textContent.trim())
        .join(' ');

    if (fullTranscript.trim()) {
        fullTranscriptSection.style.display = 'block';
        fullTranscriptEl.value = fullTranscript;
    }

    // 최종 오디오 파일 업로드 (메타데이터/Duration 복구)
    finalizeAudioUpload();

    // 메타데이터 수정 확인 모달 표시 (의도적인 종료일 때만)
    if (isIntentionalStop) {
        showEditConfirmationModal();
        isIntentionalStop = false; // Reset
    }
}

/**
 * 최종 오디오 파일 업로드 (Indexed WebM)
 */
async function finalizeAudioUpload() {
    if (!currentMeetingId || audioChunks.length === 0) return;

    console.log("Starting final audio upload to finalize metadata...");
    const token = localStorage.getItem('access_token');

    // 조각들을 하나의 Blob으로 합침 (브라우저가 이 과정에서 Duration 등을 포함한 정규 WebM 생성)
    const finalBlob = new Blob(audioChunks, { type: 'audio/webm' });

    const formData = new FormData();
    formData.append('file', finalBlob, 'recording.webm');

    try {
        const response = await fetch(`/api/upload/recording/${currentMeetingId}/finalize`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` },
            body: formData
        });

        if (response.ok) {
            console.log("✅ Audio finalized successfully.");
        } else {
            console.error("❌ Failed to finalize audio:", await response.text());
        }
    } catch (err) {
        console.error("❌ Error uploading final audio:", err);
    } finally {
        // 메모리 해제
        audioChunks = [];
    }
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
function appendTranscript(text, id) {
    if (!text.trim()) return;

    // 기존 placeholder 제거
    const placeholder = transcriptContent.querySelector('.placeholder-text');
    if (placeholder) {
        placeholder.remove();
    }

    // 새 전사 결과 추가
    const span = document.createElement('span');
    span.className = 'transcript-segment';
    if (id) span.dataset.id = id; // ID 저장 (교정용)
    span.textContent = text + ' ';
    span.style.animation = 'fadeIn 0.3s';
    transcriptContent.appendChild(span);

    // 자동 스크롤
    transcriptContent.scrollTop = transcriptContent.scrollHeight;

    // fullTranscript는 stopRecording 시점에 DOM에서 다시 읽으므로 여기서는 생략 가능하지만
    // 실시간 디버깅을 위해 일단 둠 (참조용)
    fullTranscript += text + ' ';
}

/**
 * 전사 결과 업데이트 (LLM 교정)
 */
function updateTranscript(id, newText) {
    if (!id || !newText) return;

    const span = transcriptContent.querySelector(`.transcript-segment[data-id="${id}"]`);
    if (span) {
        // [키워드] 파싱
        let displayText = newText;
        let keywordBadge = '';
        const tagMatch = newText.match(/^\[(.*?)\]\s*(.*)/);

        if (tagMatch) {
            const keyword = tagMatch[1];
            displayText = tagMatch[2];
            keywordBadge = `<span style="
                display: inline-block;
                background-color: #e7f1ff;
                color: #007bff;
                padding: 2px 6px;
                border-radius: 12px;
                font-size: 0.9em;
                font-weight: bold;
                margin-right: 6px;
                vertical-align: middle;
            ">${keyword}</span>`;
        }

        // 텍스트 교체 (Badge + Text)
        span.innerHTML = keywordBadge + displayText + ' ';

        // 시각적 피드백 (초록색 플래시)
        span.style.transition = 'background-color 0.5s ease';
        span.style.backgroundColor = 'rgba(74, 222, 128, 0.2)'; // 연한 초록색 배경
        // span.style.color = '#4ade80'; // 텍스트 색 변경은 Badge 땜에 애매하므로 배경만 Flash

        setTimeout(() => {
            span.style.backgroundColor = 'transparent';
        }, 1500);

        console.log(`Transcript corrected [${id}]: ${newText}`);
    }
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

    // [Fix] 의도적인 정지 감지
    if (btnStop) {
        btnStop.addEventListener('click', function () {
            isIntentionalStop = true;
        });
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
