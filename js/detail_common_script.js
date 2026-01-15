const urlParams = new URLSearchParams(window.location.search);
// 빌드된 페이지는 data-id 속성에서 ID를 가져오고, 없으면 쿼리에서 가져옴(하이브리드 지원)
const appTag = document.getElementById('app');
const naasId = appTag ? appTag.getAttribute('data-id') : urlParams.get('id');

if (!naasId) {
    const currentFile = window.location.pathname.split("/").pop();
    if (currentFile === "detail.html") location.href = "index.html";
}

// 날짜 변환 함수
const formatDate = (dateStr) => {          
    const d = new Date(dateStr);
    const now = new Date();
    const diff = (now - d) / (1000 * 60 * 60);
    if (diff < 24 && diff > 0) return `${Math.floor(diff)}시간 전`;
    return d.toLocaleDateString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit' }).replace(/\./g, '').replace(/ /g, '-');
};

async function loadMemberData() {
    try {
        // 경로 수정: details 폴더 내부에 있으므로 상위 폴더 참조
        const response = await fetch(`../data_export/${naasId}.json`);
        if (!response.ok) throw new Error("File Not Found");
        const data = await response.json();
        renderPage(data);
    } catch (error) {
        document.getElementById('loading').innerHTML = `
            <div class='py-20 text-slate-400'>
                <i class='fa-solid fa-circle-exclamation text-3xl mb-4 text-slate-200'></i><br>
                <span class="text-sm font-bold">데이터를 찾을 수 없습니다.</span>
            </div>`;
    }
}

function renderPage(data) {
    const { profile, analysis, recent_news: news, recent_videos: videos } = data;
    const memberName = profile.NAAS_NM;
    const partyName = profile.CURR_PLPT_NM;

    // 1. 프로필 & 메타 (클라이언트 측 재검증)
    document.getElementById('member-name').innerText = profile.NAAS_NM;
    const partyBadge = document.getElementById('member-party-badge');
    partyBadge.innerText = profile.CURR_PLPT_NM;
    partyBadge.className += getPartyClass(profile.CURR_PLPT_NM);
    
    document.getElementById('member-info').innerText = `${profile.CURR_ELECD_NM} · ${profile.RLCT_COUNT || 1}선 의원`;
    document.getElementById('member-pic').src = `../${profile.PHOTO_PATH}`;
    document.getElementById('member-pic').alt = `${memberName} 국회의원 프로필 사진`;

    // 2. 키워드
    const keywordContainer = document.getElementById('member-keywords');
    (analysis.keywords || []).forEach((kw, idx) => {
        const span = document.createElement('span');
        span.className = `keyword-badge px-3 py-1.5 rounded-xl text-[11px] font-bold shadow-sm ${idx < 3 ? 'bg-blue-600 text-white' : 'bg-slate-50 text-slate-500 border border-slate-100'}`;
        span.innerText = `#${kw}`;
        keywordContainer.appendChild(span);
    });

    // 3. SNS
    const snsContainer = document.getElementById('sns-links');
    const iconConfig = {
        facebook: { icon: 'fa-brands fa-facebook-f', color: 'bg-[#1877F2]' },
        youtube: { icon: 'fa-brands fa-youtube', color: 'bg-[#FF0000]' },
        blog: { icon: 'fa-solid fa-blog', color: 'bg-[#03C75A]' },
        instagram: { icon: 'fa-brands fa-instagram', color: 'bg-[#E4405F]' }
    };

    if (profile.SNS_INFO) {
        Object.entries(profile.SNS_INFO).forEach(([type, url]) => {
            const key = Object.keys(iconConfig).find(k => type.toLowerCase().includes(k));
            if (url && url.length > 5 && key) {
                const config = iconConfig[key];
                snsContainer.innerHTML += `
                    <a href="${url}" target="_blank" class="w-10 h-10 rounded-2xl flex items-center justify-center text-white text-lg shadow-md active:scale-90 transition-all ${config.color}">
                        <i class="${config.icon}"></i>
                    </a>`;
            }
        });
    }

    // 4. 차트 & 뉴스/영상
    renderDoughnutChart(analysis.keyword_frequency);
    renderTrendChart(analysis.trend_news);
    renderNews(news);
    renderVideos(videos);

    document.getElementById('loading').classList.add('hidden');
    const content = document.getElementById('content');
    content.classList.remove('hidden');
    setTimeout(() => content.classList.add('opacity-100'), 50);
}

function renderDoughnutChart(freqData) {
    if (!freqData) return;
    const ctx = document.getElementById('keywordChart').getContext('2d');
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: freqData.slice(0, 5).map(d => d.text),
            datasets: [{
                data: freqData.slice(0, 5).map(d => d.value),
                backgroundColor: ['#2563eb', '#3b82f6', '#60a5fa', '#93c5fd', '#bfdbfe'],
                borderWidth: 0,
                hoverOffset: 10
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '65%',
            plugins: { legend: { position: 'bottom', labels: { boxWidth: 8, font: { size: 10, weight: '600' }, padding: 15 } } }
        }
    });
}

function renderTrendChart(trendData) {
    if (!trendData) return;
    const ctx = document.getElementById('trendChart').getContext('2d');
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: trendData.labels,
            datasets: [{
                data: trendData.data,
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.05)',
                fill: true,
                tension: 0.4,
                borderWidth: 3,
                pointRadius: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: { y: { display: false }, x: { grid: { display: false }, ticks: { font: { size: 9 } } } }
        }
    });
}

function renderNews(news) {
    const list = document.getElementById('news-list');
    if (!news || news.length === 0) return document.getElementById('no-news').classList.remove('hidden');
    news.slice(0, 10).forEach(item => {
        const domain = new URL(item.originallink || item.link).hostname;
        const favicon = `https://www.google.com/s2/favicons?domain=${domain}&sz=32`;
        list.innerHTML += `<li class="p-5 active:bg-slate-50 transition-colors"><a href="${item.link}" target="_blank" class="block"><div class="flex items-center gap-2 mb-2"><img src="${favicon}" class="w-3 h-3 rounded-sm opacity-70"><span class="text-[12px] font-bold text-slate-400 uppercase tracking-tight">${item.press || 'Media'}</span><span class="text-[12px] text-slate-200">|</span><span class="text-[12px] text-slate-500">${formatDate(item.pubDate)}</span></div><h4 class="text-sm font-bold text-slate-800 leading-snug break-all">${item.title.replace(/<[^>]*>?/gm, '')}</h4></a></li>`;
    });
}

function renderVideos(videos) {
    const container = document.getElementById('video-list');
    if (!videos || videos.length === 0) return document.getElementById('no-videos').classList.remove('hidden');
    videos.slice(0, 10).forEach(v => {
        const videoId = v.url.split('v=')[1];
        container.innerHTML += `<a href="${v.url}" target="_blank" class="flex gap-4 group"><div class="w-24 h-16 rounded-2xl overflow-hidden flex-shrink-0 shadow-sm relative"><img src="https://img.youtube.com/vi/${videoId}/mqdefault.jpg" class="w-full h-full object-cover"><div class="absolute inset-0 bg-black/10 flex items-center justify-center"><i class="fa-solid fa-play text-white text-xs opacity-80"></i></div></div><div class="flex flex-col justify-center"><h4 class="text-[14px] font-bold text-slate-800 line-clamp-2 leading-tight mb-1 group-active:text-blue-600 transition-colors">${v.title}</h4><span class="text-[12px] text-slate-400 font-medium tracking-tight uppercase">${formatDate(v.collected_at)}</span></div></a>`;
    });
}

function getPartyClass(party) {
    if (party.includes('더불어민주당')) return ' bg-blue-50 text-blue-600 border-blue-100';
    if (party.includes('국민의힘')) return ' bg-red-50 text-red-600 border-red-100';
    return ' bg-slate-50 text-slate-500 border-slate-200';
}

// sns 공유 네이티브
async function _snsPopShare(title) {    
    try {
    await navigator.share({
        title: title,
        url: window.location.href,
    });
    } catch (error) {
        console.error('share wrong', error);
    }    
}

loadMemberData();