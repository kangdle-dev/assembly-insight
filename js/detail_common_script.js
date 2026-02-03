/**
 * 국회 인사이트 - 의원 상세 페이지 최종 통합 스크립트
 */

const appTag = document.getElementById('app');
const naasId = appTag ? appTag.getAttribute('data-id') : new URLSearchParams(window.location.search).get('id');
let allBills = []; 

document.addEventListener('DOMContentLoaded', () => {
    if (!naasId) return;
    loadMemberData();
});

async function loadMemberData() {
    try {
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
                <td class="p-4"><span class="px-2 py-0.5 rounded-md text-[10px] font-bold ${badgeClass}">${result}</span></td>
                <td class="p-4 font-bold text-slate-700 text-sm">
                    <div class="flex items-center gap-1">
                        <span class="truncate max-w-[150px] md:max-w-none">${bill.BILL_NAME || ""}</span>
                        <i class="fa-solid fa-arrow-up-right-from-square text-[9px] text-slate-300"></i>
                    </div>
                </td>
                <td class="p-4 text-[11px] text-slate-400 font-mono text-right">${(bill.PROPOSE_DT || "").substring(0, 10)}</td>
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
    if (!list || !news) return;
    list.innerHTML = news.slice(0, 8).map(item => `
        <li class="p-5 active:bg-slate-50 transition-colors">
            <a href="${item.link}" target="_blank" class="block">
                <div class="flex items-center gap-2 mb-2">
                    <span class="text-[12px] font-bold text-blue-500 uppercase tracking-tight">${item.press || 'Media'}</span>
                    <span class="text-[12px] text-slate-400">${item.pubDate ? new Date(item.pubDate).toLocaleDateString() : ""}</span>
                </div>
                <h4 class="text-sm font-bold text-slate-800 leading-snug line-clamp-2">${item.title.replace(/<[^>]*>?/gm, '')}</h4>
            </a>
        </li>`).join('');
}

function renderVideos(videos) {
    const container = document.getElementById('video-list');
    if (!container || !videos) return;
    container.innerHTML = videos.slice(0, 6).map(v => {
        const videoId = (v.url.split('v=')[1] || "").split('&')[0];
        return `
            <a href="${v.url}" target="_blank" class="flex gap-4 group">
                <div class="w-24 h-16 rounded-2xl overflow-hidden flex-shrink-0 shadow-sm relative">
                    <img src="https://img.youtube.com/vi/${videoId}/mqdefault.jpg" class="w-full h-full object-cover">
                    <div class="absolute inset-0 bg-black/10 flex items-center justify-center"><i class="fa-solid fa-play text-white text-xs opacity-80"></i></div>
                </div>
                <div class="flex flex-col justify-center min-w-0">
                    <h4 class="text-[14px] font-bold text-slate-800 line-clamp-2 leading-tight group-hover:text-blue-600 transition-colors">${v.title}</h4>
                    <span class="text-[12px] text-slate-400 mt-1">${v.channel || 'YouTube'}</span>
                </div>
            </a>`;
    }).join('');
}

// 트렌드 차트 및 SNS 로직 생략 (기존 함수와 동일)
function renderTrendChart(trendData) {
    if (!trendData || !document.getElementById('trendChart')) return;
    const ctx = document.getElementById('trendChart').getContext('2d');
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: trendData.labels,
            datasets: [{
                data: trendData.data,
                borderColor: '#3b82f6', backgroundColor: 'rgba(59, 130, 246, 0.05)',
                fill: true, tension: 0.4, borderWidth: 3, pointRadius: 0
            }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { display: false }, x: { grid: { display: false }, ticks: { font: { size: 9 } } } } }
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