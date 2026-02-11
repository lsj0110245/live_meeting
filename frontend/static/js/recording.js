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
let recordingSeconds = 0; // 녹음 시간 (초)
let recordingTimer = null; // 타이머 객체
let isResuming = false; // [New] 이어서 녹음하기 모드 여부

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

        // [Fix] 연결 끊김 시 처리
        if (isRecording) {
            if (!isIntentionalStop) {
                alert("서버 연결이 끊겨 녹음이 중단되었습니다.");
            }
            stopRecording();
        }
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
            if (data.is_resumed) {
                console.log('회의 이어서 녹음 시작됨');
                isResuming = true;
            }
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
    // 이어서 녹음하기인 경우 기존 ID와 메타데이터 유지
    if (isResuming && meetingMetadata) {
        console.log('Resuming with existing metadata:', meetingMetadata);
        startRecordingWithMetadata();
        return;
    }

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
        meeting_date: document.getElementById('meeting-date-input').value || null, // 빈 문자열 대신 null 전송
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
            // URL 파라미터에서 meetingId 가져오기 (이어서 녹음하기용)
            const urlParams = new URLSearchParams(window.location.search);
            const resumeMeetingId = urlParams.get('resume');

            if (resumeMeetingId) {
                meetingMetadata.meeting_id = parseInt(resumeMeetingId);
                isResuming = true;
                console.log('이어서 녹음하기 시도:', resumeMeetingId);
            }

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
        // 이어서 녹음인 경우 기존 내용을 유지
        if (!isResuming) {
            transcriptContent.innerHTML = '';
            recordingSeconds = 0;
        } else {
            // 이어서 녹음 시 이미 로드된 데이터가 있으므로 버퍼링 텍스트만 초기화 느낌으로
            bufferText.textContent = '버퍼링: 연결 중...';
        }
        updateStatus('recording', '녹음 중...');

        // 타이머 시작
        if (recordingTimer) clearInterval(recordingTimer);
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

    // WebSocket 연결 종료
    if (websocket) {
        // [New] 서버에 명시적으로 녹음 중지 알림 전송 (즉시 요약 트리거)
        if (websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({ type: 'stop_recording' }));
        }
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
    if (!currentMeetingId) return;

    // [중요] 이어서 녹음하기 모드일 때는 브라우저가 현재 세션의 오디오만 가지고 있으므로,
    // 이를 서버에 업로드하여 전체 오디오 파일을 덮어쓰지 않도록 합니다.
    if (isResuming) {
        console.log("Resuming mode: Skipping final audio upload to preserve merged server file.");
        return;
    }

    if (audioChunks.length === 0) return;

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

    // 이어서 녹음하기 체크
    const urlParams = new URLSearchParams(window.location.search);
    const resumeMeetingId = urlParams.get('resume');
    if (resumeMeetingId) {
        console.log('Resume ID detected:', resumeMeetingId);
        loadExistingData(resumeMeetingId);
    }

    // 메타데이터 제출 버튼 이벤트 연결 (즉시 시작 모드 대응)
    const submitBtn = document.getElementById('metadata-submit-btn');
    if (submitBtn) {
        submitBtn.onclick = submitMetadata;
    }

    // [Fix] 의도적인 정지 감지 및 확인절차 추가
    if (btnStop) {
        btnStop.addEventListener('click', function () {
            if (confirm('녹음을 중지하고 내용을 저장하시겠습니까?')) {
                isIntentionalStop = true;
                stopRecording();
            }
        });
    }

    // [Fix] 로고 버튼 클릭 시 정지 기능 연동 (일관성 유지)
    const logo = document.querySelector('.logo');
    if (logo) {
        logo.addEventListener('click', function (e) {
            if (isRecording) {
                e.preventDefault(); // 즉시 이동 차단
                if (confirm('현재 녹음을 종료하고 저장하시겠습니까?')) {
                    isIntentionalStop = true;
                    stopRecording();
                }
            }
        });
    }
});

// 페이지 이탈 시 정리
window.addEventListener('beforeunload', function () {
    isIntentionalStop = true; // [Fix] 페이지 이탈 시에는 경고창을 띄우지 않음
    if (websocket) {
        websocket.close();
    }
    if (mediaRecorder && isRecording) {
        mediaRecorder.stop();
    }
});

/**
 * [New] 이어서 녹음 시 기존 데이터 로드
 */
async function loadExistingData(meetingId) {
    const token = localStorage.getItem('access_token');
    if (!token) return;

    try {
        const response = await fetch(`/api/meeting/${meetingId}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) throw new Error('기존 회의 기록을 불러올 수 없습니다.');

        const meeting = await response.json();
        currentMeetingId = meeting.id;
        isResuming = true;

        // 1. 메타데이터 미리 채우기
        let formattedDate = meeting.meeting_date;
        if (formattedDate && formattedDate.includes(':')) {
            // datetime-local 형식으로 변환 (YYYY-MM-DDTHH:mm)
            formattedDate = formattedDate.substring(0, 16);
        }

        meetingMetadata = {
            title: meeting.title,
            meeting_type: meeting.meeting_type,
            meeting_date: formattedDate,
            attendees: meeting.attendees,
            writer: meeting.writer
        };

        const dateInput = document.getElementById('meeting-date-input');
        if (dateInput) dateInput.value = formattedDate || '';

        // 2. 타이머 설정
        recordingSeconds = meeting.duration || 0;
        const minutes = Math.floor(recordingSeconds / 60);
        const seconds = recordingSeconds % 60;
        timerDisplay.textContent = String(minutes).padStart(2, '0') + ':' + String(seconds).padStart(2, '0');

        // 3. 기존 전사 데이터 표시
        if (meeting.transcripts && meeting.transcripts.length > 0) {
            // Placeholder 제거
            const placeholder = transcriptContent.querySelector('.placeholder-text');
            if (placeholder) placeholder.remove();

            meeting.transcripts.sort((a, b) => a.start_time - b.start_time).forEach(t => {
                appendTranscript(t.text, t.id);
            });
            console.log(`Loaded ${meeting.transcripts.length} existing transcripts.`);
        }

        // 4. 중간 요약 표시
        if (meeting.intermediate_summaries && meeting.intermediate_summaries.length > 0) {
            meeting.intermediate_summaries.sort((a, b) => new Date(a.created_at) - new Date(b.created_at)).forEach(is => {
                appendIntermediateSummary(is.content);
            });
        }

        updateStatus('ready', '기존 기록 로드됨 (녹음 시작 가능)');

    } catch (err) {
        console.error('Failed to load existing meeting:', err);
        alert('이전 기록을 불러오지 못했습니다.');
    }
}

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
