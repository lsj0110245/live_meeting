// 인증 관련 스크립트 (로그인/회원가입)

document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');

    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }

    if (registerForm) {
        registerForm.addEventListener('submit', handleRegister);
    }
});

async function handleLogin(e) {
    e.preventDefault();
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;

    const formData = new FormData();
    formData.append('username', email);
    formData.append('password', password);

    try {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const data = await response.json();
            localStorage.setItem('access_token', data.access_token);
            window.location.href = '/';
        } else {
            let errorMessage;
            try {
                const error = await response.json();
                errorMessage = error.detail || '오류가 발생했습니다.';
            } catch (e) {
                // JSON 파싱 실패 시 텍스트로 읽기 (500 에러 등)
                errorMessage = await response.text();
            }
            alert('로그인 실패: ' + errorMessage);
        }
    } catch (err) {
        alert('서버 연결 오류');
        console.error(err);
    }
}

async function handleRegister(e) {
    e.preventDefault();

    const email = document.getElementById('email').value;
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const passwordConfirm = document.getElementById('password-confirm').value;

    // 유효성 검사 (사용자 요청 사항)

    // 1. 이름은 10자 이내
    if (username.length > 10) {
        alert('이름은 10자 이내로 입력해주세요.');
        return;
    }

    // 2. 비밀번호는 4자리 이상
    if (password.length < 4) {
        alert('비밀번호는 4자리 이상으로 설정해주세요.');
        return;
    }

    // 3. 이메일 형식 (@email.com 형식으로 양식 꼭 맞추고 - 일반적인 이메일 형식 체크)
    // "형식"이라는 말이 표준 포맷을 의미하는 것으로 해석되나, 혹시 모를 오해를 방지하기 위해 표준 정규식 사용
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
        alert('올바른 이메일 형식을 입력해주세요. (예: user@email.com)');
        return;
    }

    if (password !== passwordConfirm) {
        alert('비밀번호가 일치하지 않습니다.');
        return;
    }

    try {
        const response = await fetch('/api/auth/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                email: email,
                username: username,
                password: password
            })
        });

        if (response.ok) {
            alert('회원가입이 완료되었습니다. 로그인해주세요.');
            window.location.href = '/login';
        } else {
            const error = await response.json();
            alert('가입 실패: ' + (error.detail || '오류가 발생했습니다.'));
        }
    } catch (err) {
        alert('서버 연결 오류');
        console.error(err);
    }
}
