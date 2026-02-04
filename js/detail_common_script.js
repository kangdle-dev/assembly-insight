/**
 * 국회 인사이트 - 의원 상세 페이지 최종 통합 스크립트
 */

const appTag = document.getElementById('app');
const naasId = appTag ? appTag.getAttribute('data-id') : new URLSearchParams(window.location.search).get('id');
let allBills = []; 
let allNews = [];
let allVideos = [];
let memberNameMap = {};
const MEMBERS_22ND_NAME = "members_22nd_name.json"; // 22대 의원 이름 매핑 파일명

document.addEventListener('DOMContentLoaded', () => {
    if (!naasId) return;
    loadMemberData();
});

async function loadMemberData() {
    try {
        // 이름 매핑을 먼저 로드
        await loadMemberMap();

        const response = await fetch(`/data_export/${naasId}.json`);        

        if (!response.ok) throw new Error("File Not Found");
        const data = await response.json();
        renderPage(data);
    } catch (error) {
        console.error("데이터 로드 실패:", error);
        const loadingEl = document.getElementById('loading');
        if (loadingEl) loadingEl.innerHTML = `<div class='py-20 text-slate-400 font-bold'>데이터를 찾을 수 없습니다.</div>`;
    }
}

function renderPage(data) {
    const { profile, analysis, recent_news, recent_videos, recent_bills } = data;

    // 1. 프로필 정보 (상임위 등 상세 정보 포함)
    const infoEl = document.getElementById('member-info');
    if (infoEl) {
        const committee = profile.COMMITTEE_NM || "소속 상임위 확인 중";
        infoEl.innerHTML = `
            <div class="text-blue-600 font-bold mb-1">${committee}</div>
            <div class="text-slate-500 text-xs">${profile.CURR_ELECD_NM || ""} · ${profile.RLCT_COUNT || 1}선 의원</div>
        `;
    }

    // 2. AI 요약 주입 (템플릿 내부 P 태그 타겟팅)
    const summaryEl = document.querySelector('#content section.border-l-\\[12px\\] p');
    if (summaryEl) summaryEl.innerText = analysis.ai_policy_summary || "";

    // 상세정보
    renderDetailedInfo(profile);    

    // 3. 차트 렌더링
    renderPolicyChart(analysis.policy_stats);
    renderTrendChart(analysis.trend_news);
    renderKeywordChart(analysis.keyword_frequency);
    renderRelatedMemberTags(recent_news);

    // 4. 리스트 렌더링 (더보기 기능 포함)
    renderBillsTable(recent_bills);
    renderNews(recent_news);
    renderVideos(recent_videos);
    renderSNSLinks(profile.SNS_INFO);

    // 5. 화면 표시 전환
    const loadingEl = document.getElementById('loading');
    const contentEl = document.getElementById('content');
    if (loadingEl) loadingEl.classList.add('hidden');
    if (contentEl) {
        contentEl.classList.remove('hidden');
        setTimeout(() => contentEl.classList.add('opacity-100'), 50);
    }
}

function renderDetailedInfo(profile) {
    // 기본 정보
    document.getElementById('det-han-name').innerText = profile.NAAS_CH_NM || "-";
    document.getElementById('det-en-name').innerText = profile.NAAS_EN_NM || "-";
    document.getElementById('det-birth').innerText = `${profile.BIRDY_DT} (${profile.BIRDY_DIV_CD})`;
    document.getElementById('det-room').innerText = profile.OFFM_RNUM_NO || "-";

    // 보좌진
    document.getElementById('det-aide').innerText = profile.AIDE_NM || "-";
    document.getElementById('det-chief').innerText = profile.CHF_SCRT_NM || "-";

    // 학력 및 경력 파싱 (BRF_HST 텍스트 활용)
    const historyText = profile.BRF_HST || "";
    console.log(historyText);
    // 주요 경력 로직
    if(historyText) {        
        const eduLines = historyText.trim().split('\r\n');
         document.getElementById('det-edu').innerHTML = eduLines
             .map(line => `<li class="flex items-start gap-1">${line.replace('&middot;', '').trim()}</li>`)
             .join('');
    }    
}

// 입법 성과 차트 (중앙 텍스트 추가)
function renderPolicyChart(stats) {
    if (!stats || !document.getElementById('policyChart')) return;
    const ctx = document.getElementById('policyChart').getContext('2d');
    
    const centerTextPlugin = {
        id: 'centerText',
        afterDraw(chart) {
            const { ctx, chartArea: { width, height, top } } = chart;
            ctx.save();
            ctx.font = 'bold 15px Pretendard';
            ctx.fillStyle = '#1e293b';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(`총 ${stats.total}건`, width / 2, height / 2 + top);
            ctx.restore();
        }
    };

    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['가결', '반영', '계류', '실패'],
            datasets: [{
                data: [stats.passed, stats.reflected, stats.pending, stats.failed],
                backgroundColor: ['#2563eb', '#60a5fa', '#cbd5e1', '#f87171'],
                borderWidth: 0,
                hoverOffset: 12
            }]
        },
        options: {
            cutout: '75%',
            plugins: { legend: { position: 'bottom', labels: { boxWidth: 8, font: { size: 10 } } } }
        },
        plugins: [centerTextPlugin]
    });
}

// 법안 테이블 (10개 제한 및 상세 링크)
function renderBillsTable(bills) {
    const tbody = document.querySelector('#bills-table tbody');
    const tfoot = document.getElementById('more-btn-container');
    
    if (!tbody) return;

    allBills = bills || [];
    const initialBills = allBills.slice(0, 10);
    
    const getRowHtml = (bill) => {
        const result = bill.PROC_RESULT || "계류";
        const link = `https://likms.assembly.go.kr/bill/billDetail.do?billId=${bill.BILL_ID || ""}`;
        let badgeClass = "bg-slate-100 text-slate-500";
        if (result.includes("가결")) badgeClass = "bg-blue-600 text-white";
        else if (result.includes("반영")) badgeClass = "bg-sky-100 text-sky-600";
        else if (result.includes("폐기")) badgeClass = "bg-red-50 text-red-500";

        return `
            <tr class="hover:bg-slate-50/50 transition-colors border-b border-slate-50 cursor-pointer" onclick="window.open('${link}', '_blank')">
                <td class="p-4"><span class="px-2 py-0.5 rounded-md text-[12px] font-bold ${badgeClass}">${result}</span></td>
                <td class="p-4 font-bold text-slate-700 text-[15px]">
                    <div class="flex items-center gap-1">
                        <span class="truncate max-w-[150px] md:max-w-none">${bill.BILL_NAME || ""}</span>
                        <i class="fa-solid fa-arrow-up-right-from-square text-[11px] text-slate-300"></i>
                    </div>
                </td>
                <td class="p-4 text-[12px] text-slate-400 font-mono text-right">${(bill.PROPOSE_DT || "").substring(0, 10)}</td>
            </tr>`;
    };

    tbody.innerHTML = initialBills.map(getRowHtml).join('');
    // 더보기 버튼 동적 노출
    if (allBills.length > 10 && tfoot) {
        tfoot.innerHTML = `
            <tr>
                <td colspan="3" class="p-0">
                    <button onclick="expandBills()" class="w-full py-4 text-xs font-bold text-slate-400 hover:text-blue-600 transition-colors bg-slate-50/30">
                        법안 더보기 (${allBills.length - 10}건) <i class="fa-solid fa-chevron-down ml-1"></i>
                    </button>
                </td>
            </tr>`;
    }
}

function expandBills() {
    const tbody = document.querySelector('#bills-table tbody');
    const tfoot = document.getElementById('more-btn-container');
    
    tbody.innerHTML = allBills.map(bill => {
        const result = bill.PROC_RESULT || "계류";
        const link = `https://likms.assembly.go.kr/bill/billDetail.do?billId=${bill.BILL_ID || ""}`;
        let badgeClass = "bg-slate-100 text-slate-500";
        if (result.includes("가결")) badgeClass = "bg-blue-600 text-white";
        else if (result.includes("반영")) badgeClass = "bg-sky-100 text-sky-600";
        else if (result.includes("폐기")) badgeClass = "bg-red-50 text-red-500";

        return `
            <tr class="hover:bg-slate-50/50 transition-colors border-b border-slate-50 cursor-pointer" onclick="window.open('${link}', '_blank')">
                <td class="p-4"><span class="px-2 py-0.5 rounded-md text-[10px] font-bold ${badgeClass}">${result}</span></td>
                <td class="p-4 font-bold text-slate-700 text-sm">${bill.BILL_NAME || ""}</td>
                <td class="p-4 text-[11px] text-slate-400 font-mono text-right">${(bill.PROPOSE_DT || "").substring(0, 10)}</td>
            </tr>`;
    }).join('');
    
    if (tfoot) tfoot.innerHTML = '';
}

// 뉴스 및 영상 렌더링 (기존 로직 유지)
function renderNews(news) {
    const list = document.getElementById('news-list');
    const moreBtnContainer = document.getElementById('more-news-container');
    if (!list) return;

    allNews = news || [];
    const initialNews = allNews.slice(0, 10); // 초기 10개    

    const getNewsHtml = (item) => {
        return ` 
            <li class="p-5 active:bg-slate-50 transition-colors">
                <a href="${item.originallink}" target="_blank" class="block">
                    <div class="flex items-center gap-2 mb-2">
                        <span class="text-[12px] font-bold text-blue-500 uppercase tracking-tight">${item.press || 'Media'}</span>
                        <span class="text-[12px] text-slate-400">${item.pubDate ? new Date(item.pubDate).toLocaleString() : ""}</span>
                    </div>
                    <h4 class="text-[15px] font-bold text-slate-800 leading-snug line-clamp-2">${item.title.replace(/<[^>]*>?/gm, '')}</h4>
                </a>
            </li>`;
    };
    list.innerHTML = initialNews.map(getNewsHtml).join('');

    // 더보기 버튼 동적 노출
    if (allNews.length > 10 && moreBtnContainer) {
        moreBtnContainer.innerHTML = `
            <button onclick="expandNews()" class="w-full py-4 text-sm font-bold text-slate-400 hover:text-blue-600 transition-colors bg-slate-50/30">
                뉴스 더보기 (${allNews.length - 10}건) <i class="fa-solid fa-chevron-down ml-1"></i>
            </button>
        `;
    }
}

// 뉴스 확장 함수
function expandNews() {
    const list = document.getElementById('news-list');
    const moreBtnContainer = document.getElementById('more-news-container');    

    // 전체 리스트 재렌더링 (또는 추가분만 append 가능)
    list.innerHTML = allNews.map(item => {
        const dateStr = item.pubDate ? new Date(item.pubDate).toLocaleString('ko-KR') : "";
        return `
            <li class="p-5 active:bg-slate-50 transition-colors border-b border-slate-50">
                <a href="${item.originallink}" target="_blank" class="block">
                    <div class="flex items-center gap-2 mb-2">
                        <span class="text-[12px] font-bold text-blue-500 uppercase tracking-tight">${item.press || 'Media'}</span>
                        <span class="text-[12px] text-slate-400">${dateStr}</span>
                    </div>
                    <h4 class="text-sm font-bold text-slate-800 leading-snug">${item.title.replace(/<[^>]*>?/gm, '')}</h4>
                </a>
            </li>`;
    }).join('');

    if (moreBtnContainer) moreBtnContainer.innerHTML = ''; // 버튼 제거
}

function renderVideos(videos) {
    const container = document.getElementById('video-list');
    const moreBtnContainer = document.getElementById('more-video-container');
    
    if (!container) return;
    allVideos = videos || [];
    const initialVideos = allVideos.slice(0, 10); // 초기 10개    

    const getVideoHtml = (item) => {
        const videoId = (item.url.split('v=')[1] || "").split('&')[0];
        return `
            <a href="${item.url}" target="_blank" class="flex gap-4 group">
                <div class="w-40 h-24 rounded-2xl overflow-hidden flex-shrink-0 shadow-sm relative">
                    <img src="https://img.youtube.com/vi/${videoId}/mqdefault.jpg" class="w-full h-full object-cover">
                    <div class="absolute inset-0 bg-black/10 flex items-center justify-center"><i class="fa-solid fa-play text-white text-xs opacity-80"></i></div>
                </div>
                <div class="flex flex-col justify-center min-w-0">
                    <h4 class="text-[15px] font-bold text-slate-800 line-clamp-2 leading-tight group-hover:text-blue-600 transition-colors">${item.title}</h4>
                    <span class="text-[12px] text-slate-400 mt-1">${item.channel || 'YouTube'}</span>
                </div>
            </a>`;
    }
    container.innerHTML = initialVideos.map(getVideoHtml).join('');

    // 더보기 버튼 동적 노출
    if (allVideos.length > 10 && moreBtnContainer) {
        moreBtnContainer.innerHTML = `
            <button onclick="expandVideos()" class="w-full py-4 text-sm font-bold text-slate-400 hover:text-blue-600 transition-colors bg-slate-50/30">
                영상 더보기 (${allVideos.length - 10}건) <i class="fa-solid fa-chevron-down ml-1"></i>
            </button>
        `;
    }
}

// 영상 확장 함수
function expandVideos() {
    const container = document.getElementById('video-list');
    const moreBtnContainer = document.getElementById('more-video-container');

    if (moreBtnContainer) moreBtnContainer.innerHTML = ''; // 버튼 제거
}

// 트렌드 차트 및 SNS 로직 생략 (기존 함수와 동일)
function renderTrendChart(trendData) {
    console.log(trendData);
    if (!trendData || !document.getElementById('trendChart')) return;
    const ctx = document.getElementById('trendChart').getContext('2d');
    
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: trendData.labels,
            datasets: [
                {
                    // 1. 의원 본인 데이터 (메인 파란색 실선)
                    label: '현재 의원',
                    data: trendData.data,
                    borderColor: '#3b82f6', 
                    backgroundColor: 'rgba(59, 130, 246, 0.08)',
                    fill: true, 
                    tension: 0.4, 
                    borderWidth: 3,
                    pointRadius: 0,
                    pointHoverRadius: 6,
                    zIndex: 10
                },
                {
                    // 2. 22대 의원 평균 데이터 (배경 회색 점선)
                    label: '22대 평균',
                    data: trendData.avg_data, // JSON에 포함된 평균 데이터 배열
                    borderColor: '#cbd5e1', 
                    borderWidth: 2,
                    borderDash: [5, 5], // 점선 스타일
                    fill: false, 
                    tension: 0.4, 
                    pointRadius: 0,
                    pointHoverRadius: 0,
                    zIndex: 5
                }
            ]
        },
        options: { 
            responsive: true, 
            maintainAspectRatio: false, 
            interaction: {
                mode: 'index', // 마우스 올렸을 때 두 데이터 한 번에 비교
                intersect: false,
            },
            plugins: { 
                legend: { 
                    display: true, 
                    position: 'top',
                    align: 'end',
                    labels: { 
                        boxWidth: 8, 
                        usePointStyle: true,
                        font: { size: 10, weight: '600' } 
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(255, 255, 255, 0.95)',
                    titleColor: '#1e293b',
                    bodyColor: '#475569',
                    borderColor: '#e2e8f0',
                    borderWidth: 1,
                    padding: 10,
                    titleFont: { weight: 'bold' },
                    callbacks: {
                        label: function(context) {
                            return ` ${context.dataset.label}: ${context.parsed.y}pt`;
                        }
                    }
                }
            }, 
            scales: { 
                y: { 
                    display: false, // 복잡함 제거를 위해 Y축 숨김
                    beginAtZero: true 
                }, 
                x: { 
                    grid: { display: false }, 
                    ticks: { 
                        font: { size: 10 }, 
                        color: '#94a3b8',
                        maxRotation: 0
                    } 
                } 
            } 
        }
    });
}

function renderSNSLinks(snsInfo) {
    const container = document.getElementById('sns-links');
    if (!container || !snsInfo) return;
    const config = {
        facebook: { icon: 'fa-brands fa-facebook-f', color: 'bg-[#1877F2]' },
        youtube: { icon: 'fa-brands fa-youtube', color: 'bg-[#FF0000]' },
        blog: { icon: 'fa-solid fa-blog', color: 'bg-[#03C75A]' },
        instagram: { icon: 'fa-brands fa-instagram', color: 'bg-[#E4405F]' }
    };
    let html = '';
    Object.entries(snsInfo).forEach(([type, url]) => {
        const key = Object.keys(config).find(k => type.toLowerCase().includes(k));
        if (url && url.length > 5 && key) {
            html += `<a href="${url}" target="_blank" class="w-10 h-10 rounded-2xl flex items-center justify-center text-white text-lg shadow-md active:scale-90 transition-all ${config[key].color}"><i class="${config[key].icon}"></i></a>`;
        }
    });
    container.innerHTML = html;
}

async function _snsPopShare(title) {    
    try { await navigator.share({ title: title, url: window.location.href }); } catch (e) { console.error(e); }    
}

/**
 * 축소된 상단 바를 고려한 섹션 스크롤 로직
 */
function scrollToSection(sectionId) {
    const element = document.getElementById(sectionId);
    if (!element) return;

    // 네비게이션 바 높이(h-14/16) + 여백(20px) 설정
    const navHeight = document.querySelector('nav').offsetHeight;
    const elementPosition = element.getBoundingClientRect().top;
    const offsetPosition = elementPosition + window.pageYOffset - navHeight - 20;

    window.scrollTo({
        top: offsetPosition,
        behavior: "smooth"
    });

    // 탭 활성화 스타일 업데이트
    updateActiveTab(sectionId);
}

/**
 * 모바일 상세 프로필 펼치기/접기
 */
function toggleMobileProfile() {
    const content = document.getElementById('mobile-profile-content');
    const btn = document.getElementById('profile-more-btn');
    const gradient = document.getElementById('profile-gradient');

    if (content.style.maxHeight === 'none' || content.classList.contains('expanded')) {
        // 다시 접기 (필요한 경우)
        content.style.maxHeight = '400px';
        content.classList.remove('expanded');
        btn.innerHTML = '상세정보 더보기 <i class="fa-solid fa-chevron-down"></i>';
        if (gradient) gradient.classList.remove('hidden');
    } else {
        // 펼치기
        content.style.maxHeight = 'none';
        content.classList.add('expanded');
        btn.innerHTML = '상세정보 접기 <i class="fa-solid fa-chevron-up"></i>';
        if (gradient) gradient.classList.add('hidden');
    }
}

/**
 * 키워드 빈도수 가로 바 차트 렌더링
 */
function renderKeywordChart(keywordFrequency) {
    if (!keywordFrequency || !document.getElementById('keywordChart')) return;

    const ctx = document.getElementById('keywordChart').getContext('2d');
    const topKeywords = keywordFrequency.slice(0, 7); // 상위 7개 추출

    new Chart(ctx, {
        type: 'bar', // 가로 바 차트
        data: {
            labels: topKeywords.map(k => k.text),
            datasets: [{
                label: '언급 횟수',
                data: topKeywords.map(k => k.value),
                backgroundColor: 'rgba(59, 130, 246, 0.8)',
                borderRadius: 8,
                barThickness: 15
            }]
        },
        options: {
            indexAxis: 'y', // 가로 방향 설정
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { display: false }, ticks: { display: false }, border: { display: false } },
                y: { grid: { display: false }, border: { display: false }, ticks: { font: { size: 11, weight: 'bold' } } }
            }
        }
    });
}

/**
 * 1. 의원 이름 매핑 데이터 로드 (빌드된 JSON 활용)
 */
async function loadMemberMap() {
    try {
        const response = await fetch(`/data_export/${MEMBERS_22ND_NAME}`);        
        const data = await response.json();
        
        // 데이터가 리스트 형태라면 {코드: 이름} 딕셔너리로 변환
        if (Array.isArray(data)) {
            data.forEach(m => {
                const code = m.NAAS_CD || m.naas_cd;
                const name = m.NAAS_NM || m.hg_nm || m.HG_NM;
                if (code) memberNameMap[code] = name;
            });
        } else {
            memberNameMap = data; // 이미 딕셔너리 형태인 경우
        }
    } catch (error) {
        console.error("이름 매핑 파일 로드 실패:", error);
    }
}

/**
 * 2. 관련 의원 해시태그 렌더링
 */
function renderRelatedMemberTags(newsList) {
    const container = document.getElementById('related-member-tags');
    if (!newsList || !container) return;

    // 빈도수 집계
    const counts = {};
    newsList.forEach(news => {
        if (news.related_members) {
            news.related_members.forEach(id => {
                if (id !== naasId) counts[id] = (counts[id] || 0) + 1;
            });
        }
    });

    const sortedMembers = Object.entries(counts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 10); // 상위 10명 추출

    if (sortedMembers.length === 0) {
        container.innerHTML = '<p class="text-slate-300 text-xs italic">최근 공동 언급된 동료 의원이 없습니다.</p>';
        return;
    }

    container.innerHTML = sortedMembers.map(([id, count], index) => {
        // 매핑 테이블에서 이름 찾기
        const name = memberNameMap[id] || `의원(${id.substring(0,4)})`;
        
        // 순위에 따른 폰트 크기 및 색상 차등 (가독성 최적화)
        let sizeClass = "text-[12px] px-3 py-1.5 bg-slate-50 text-slate-500 border border-slate-100"; // 기본
        if (index === 0) sizeClass = "text-[18px] px-5 py-2 bg-blue-600 text-white font-black shadow-md"; // 1위
        else if (index < 4) sizeClass = "text-[15px] px-4 py-2 bg-blue-50 text-blue-700 font-bold border border-blue-100"; // 2~4위

        return `
            <a href="./${name}.html" 
               class="inline-block rounded-full transition-all hover:scale-110 active:scale-95 shadow-sm ${sizeClass}"
               title="공동 뉴스 출연 ${count}회">
                #${name}
            </a>`;
    }).join('');
}