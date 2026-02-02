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

            // 사용자 정보 불러와서 프로필 이미지 업데이트
            fetch('/api/users/me', {
                headers: { 'Authorization': `Bearer ${token}` }
            })
                .then(res => {
                    if (res.ok) return res.json();
                    throw new Error('Failed to fetch user');
                })
                .then(user => {
                    if (user.profile_image_path) {
                        const profileLink = document.getElementById('navbar-profile-link');
                        if (profileLink) {
                            let imgPath = user.profile_image_path;
                            if (!imgPath.startsWith('/')) imgPath = '/' + imgPath;
                            imgPath = imgPath.replace(/\\/g, '/');

                            profileLink.innerHTML = `<img src="${imgPath}" alt="Profile">`;
                        }
                    }
                })
                .catch(err => {
                    console.error('Profile fetch error:', err);
                    if (err.message === 'Failed to fetch user') {
                        // 토큰이 만료되었거나 유효하지 않은 경우 로그아웃 처리 가능
                        // logout(); 
                    }
                });
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
