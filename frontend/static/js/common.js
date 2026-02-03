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
                    if (res.status === 403 || res.status === 401) {
                        throw new Error('Unauthorized');
                    }
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
                    if (err.message === 'Unauthorized') {
                        // 403/401 에러 시: 회원이 아니거나 인증 만료
                        alert('회원이 아닙니다.');
                        logout();
                    } else {
                        console.error('Profile fetch error:', err);
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

// =========================================
// Loading Overlay & Progress Helpers
// =========================================

/**
 * Show global loading overlay with spinner
 * @param {string} message - Optional message to display
 */
function showLoading(message = '잠시만 기다려주세요...') {
    const overlay = document.getElementById('loading-overlay');
    const msgEl = document.getElementById('loading-message');
    const progressContainer = document.getElementById('progress-container');

    if (overlay && msgEl) {
        msgEl.textContent = message;
        if (progressContainer) progressContainer.classList.add('hidden'); // Hide progress bar for simple loading
        overlay.classList.remove('hidden');
    }
}

/**
 * Show loading overlay with progress bar
 * @param {string} message - Message to display
 * @param {number} percent - Initial percentage (0-100)
 */
function showProgress(message = '처리 중...', percent = 0) {
    const overlay = document.getElementById('loading-overlay');
    const msgEl = document.getElementById('loading-message');
    const progressContainer = document.getElementById('progress-container');

    if (overlay && msgEl && progressContainer) {
        msgEl.textContent = message;
        progressContainer.classList.remove('hidden');
        updateProgress(percent);
        overlay.classList.remove('hidden');
    }
}

/**
 * Update the progress bar percentage
 * @param {number} percent - Percentage (0-100)
 */
function updateProgress(percent) {
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');

    if (progressBar && progressText) {
        // Ensure percent is between 0 and 100
        const p = Math.max(0, Math.min(100, Math.round(percent)));
        progressBar.style.width = p + '%';
        progressText.textContent = p + '%';
    }
}

/**
 * Hide global loading overlay
 */
function hideLoading() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        setTimeout(() => {
            overlay.classList.add('hidden');
            // Reset progress bar
            updateProgress(0);
        }, 500); // Slight delay for smoother UX
    }
}
