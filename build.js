const fs = require('fs');
const path = require('path');

const DATA_DIR = path.join(__dirname, 'data_export');
const TEMPLATE_PATH = path.join(__dirname, 'detail_template.html');
const OUTPUT_DIR = path.join(__dirname, 'details');

if (!fs.existsSync(OUTPUT_DIR)) fs.mkdirSync(OUTPUT_DIR, { recursive: true });

function build() {
    // members_all.json을 제외한 모든 의원별 JSON 읽기
    const files = fs.readdirSync(DATA_DIR).filter(f => f.endsWith('.json') && f !== 'members_all.json');
    const template = fs.readFileSync(TEMPLATE_PATH, 'utf8');

    console.log(`🚀 빌드 시작: 총 ${files.length}개의 페이지 생성 중...`);

    files.forEach(file => {
        try {
            const data = JSON.parse(fs.readFileSync(path.join(DATA_DIR, file), 'utf8'));
            const p = data.profile;
            
            let html = template
                .replace(/{{MEMBER_ID}}/g, p.NAAS_CD)
                .replace(/{{MEMBER_NAME}}/g, p.NAAS_NM)
                .replace(/{{PARTY_NAME}}/g, p.CURR_PLPT_NM)
                .replace(/{{PHOTO_PATH}}/g, p.PHOTO_PATH);

            fs.writeFileSync(path.join(OUTPUT_DIR, `${p.NAAS_CD}.html`), html);
        } catch (e) {
            console.error(`Error processing ${file}:`, e);
        }
    });

    console.log("✅ 빌드 완료!");
}

build();