// 공통 JavaScript (인증 체크, 로그아웃 등)

document.addEventListener('DOMContentLoaded', () => {
    checkLoginStatus();
});

function checkLoginStatus() {
    const token = localStorage.getItem('access_token');
    const navAuth = document.getElementById('nav-auth');
    const navUser = document.getElementById('nav-user');

    if (navAuth && navUser) {
        if (token) {
            // 로그인 상태
            navAuth.classList.add('hidden');
            navUser.classList.remove('hidden');
        } else {
            // 비로그인 상태
            navAuth.classList.remove('hidden');
            navUser.classList.add('hidden');
        }
    }
}

function logout() {
    localStorage.removeItem('access_token');
    alert('로그아웃 되었습니다.');
    window.location.href = '/login';
}

// Fetch Wrapper with Auth Header (Optional Helper)
async function authFetch(url, options = {}) {
    const token = localStorage.getItem('access_token');
    if (!token) {
        window.location.href = '/login';
        throw new Error('No token found');
    }
    
    options.headers = {
        ...options.headers,
        'Authorization': `Bearer ${token}`
    };
    
    return fetch(url, options);
}
