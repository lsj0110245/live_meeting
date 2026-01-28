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
            const error = await response.json();
            alert('로그인 실패: ' + (error.detail || '오류가 발생했습니다.'));
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
