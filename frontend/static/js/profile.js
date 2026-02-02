document.addEventListener('DOMContentLoaded', async () => {
    await loadProfile();

    // 이미지 업로드 리스너
    document.getElementById('image-upload').addEventListener('change', uploadImage);
});

async function loadProfile() {
    const token = localStorage.getItem('access_token');
    if (!token) {
        window.location.href = '/login';
        return;
    }

    try {
        const response = await fetch('/api/users/me', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (response.ok) {
            const user = await response.json();

            // 폼 데이터 채우기
            document.getElementById('email').value = user.email || '';
            document.getElementById('username').value = user.username || '';
            document.getElementById('team_name').value = user.team_name || '';
            document.getElementById('age').value = user.age || '';
            document.getElementById('phone_number').value = user.phone_number || '';

            // 프로필 이미지 표시
            if (user.profile_image_path) {
                // 경로 수정 (backend/media/... -> /media/...)
                // DB에는 'media/profiles/filename.jpg' 형태로 저장됨
                // Docker bind mount 설정에 따라 /media/... 로 접근 가능해야 함
                // main.py에서 app.mount("/media", ...) 했는지 확인 필요

                // path가 절대경로일 수도 있고 상대경로일 수도 있음.
                // 상대경로인 경우 media/ 로 시작하면 /를 붙여줌
                let imgPath = user.profile_image_path;
                if (!imgPath.startsWith('/')) {
                    imgPath = '/' + imgPath;
                }
                // Docker path adjustment: remove 'backend/' if present (though typically it assumes root relative)
                // Just use /media/... assuming backend/media is mounted to /media URL

                // 윈도우 경로 역슬래시 처리
                imgPath = imgPath.replace(/\\/g, '/');

                const imgEl = document.getElementById('profile-img');
                const placeholder = document.getElementById('profile-placeholder');

                imgEl.src = imgPath;
                imgEl.style.display = 'block';
                placeholder.style.display = 'none';
            }

        } else {
            console.error('Failed to load profile');
            if (response.status === 401) window.location.href = '/login';
        }
    } catch (err) {
        console.error('Error loading profile:', err);
    }
}

async function updateProfile() {
    const token = localStorage.getItem('access_token');
    const data = {
        username: document.getElementById('username').value,
        team_name: document.getElementById('team_name').value,
        age: document.getElementById('age').value ? parseInt(document.getElementById('age').value) : null,
        phone_number: document.getElementById('phone_number').value
    };

    try {
        const response = await fetch('/api/users/me', {
            method: 'PUT',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            alert('프로필이 업데이트되었습니다.');
        } else {
            const error = await response.json();
            alert('업데이트 실패: ' + (error.detail || '알 수 없는 오류'));
        }
    } catch (err) {
        console.error('Error updating profile:', err);
        alert('업데이트 중 오류가 발생했습니다.');
    }
}

async function uploadImage(e) {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    const token = localStorage.getItem('access_token');

    try {
        const response = await fetch('/api/users/me/image', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            },
            body: formData
        });

        if (response.ok) {
            // 이미지 즉시 반영을 위해 다시 로드하거나 FileReader 사용
            const reader = new FileReader();
            reader.onload = function (e) {
                const imgEl = document.getElementById('profile-img');
                const placeholder = document.getElementById('profile-placeholder');
                imgEl.src = e.target.result;
                imgEl.style.display = 'block';
                placeholder.style.display = 'none';
            };
            reader.readAsDataURL(file);
            alert('프로필 사진이 변경되었습니다.');
        } else {
            const error = await response.json();
            alert('이미지 업로드 실패: ' + (error.detail || '알 수 없는 오류'));
        }
    } catch (err) {
        console.error('Error uploading image:', err);
        alert('이미지 업로드 중 오류가 발생했습니다.');
    }
}
