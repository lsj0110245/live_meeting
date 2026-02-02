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
let recordingTimer = null;
let recordingSeconds = 0;
let fullTranscript = "";

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

    websocket.onopen = function() {
        console.log('WebSocket 연결됨');
        updateStatus('connected', '연결됨');
    };

    websocket.onmessage = function(event) {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };

    websocket.onclose = function() {
        console.log('WebSocket 연결 끊김');
        updateStatus('disconnected', '연결 끊김');
        stopRecording();
    };

    websocket.onerror = function(error) {
        console.error('WebSocket 에러:', error);
        updateStatus('disconnected', '연결 오류');
    };
}

/**
 * WebSocket 메시지 처리
 */
function handleWebSocketMessage(data) {
    switch(data.type) {
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
            
        case 'error':
            console.error('서버 에러:', data.message);
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
 * 녹음 시작
 */
async function startRecording() {
    try {
        // 마이크 권한 요청
        const stream = await navigator.mediaDevices.getUserMedia({ 
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
                sampleRate: 16000
            } 
        });

        // WebSocket 연결
        if (!websocket || websocket.readyState !== WebSocket.OPEN) {
            connectWebSocket();
            // 연결 완료 대기
            await new Promise(resolve => setTimeout(resolve, 1000));
        }

        // MediaRecorder 설정
        const options = { mimeType: 'audio/webm;codecs=opus' };
        mediaRecorder = new MediaRecorder(stream, options);

        mediaRecorder.ondataavailable = function(event) {
            if (event.data.size > 0 && websocket && websocket.readyState === WebSocket.OPEN) {
                // 오디오 청크를 WebSocket으로 전송
                websocket.send(event.data);
            }
        };

        mediaRecorder.onstop = function() {
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
        alert('마이크 접근 권한이 필요합니다.');
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

// 페이지 로드 시 WebSocket 연결
document.addEventListener('DOMContentLoaded', function() {
    // 로그인 확인
    const token = localStorage.getItem('access_token');
    if (!token) {
        window.location.href = '/login';
        return;
    }
    
    // WebSocket 연결
    connectWebSocket();
});

// 페이지 이탈 시 정리
window.addEventListener('beforeunload', function() {
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
`;
document.head.appendChild(style);
