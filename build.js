const { MongoClient } = require('mongodb');
const fs = require('fs-extra');
const path = require('path');
require('dotenv').config();

const MONGO_URI = process.env.MONGO_URI;
const DB_NAME = 'assembly_insight';
const TEMPLATE_PATH = path.join(__dirname, 'templates', 'detail_template.html');
const HTML_OUTPUT_DIR = path.join(__dirname, 'members', '22_details');

async function buildHtmlWithJoin() {
    const client = new MongoClient(MONGO_URI);

    try {
        await client.connect();
        const db = client.db(DB_NAME);

        // 1. Aggregate를 이용한 테이블 Join 로직
        const membersWithPolicy = await db.collection('members_policy').aggregate([
            {
                $lookup: {
                    from: "members",           // Join할 대상 컬렉션
                    localField: "naas_cd",        // members_policy의 필드
                    foreignField: "NAAS_CD",     // members의 필드 (이름 필드명 확인 필요)
                    as: "profile"              // 합쳐진 결과가 담길 배열 이름
                }
            },
            {
                $unwind: "$profile"            // 배열을 객체로 풀기
            },
            {
                $project: {                    // 빌드에 필요한 필드만 선택
                    name: 1,
                    ai_summary: 1,
                    naas_cd: 1,
                    archivement_rate: "$analysis_stats.achievement_rate",
                    party_name: "$profile.CURR_PLPT_NM",
                    region_name: "$profile.CURR_ELECD_NM",
                    photo_path: "$profile.PHOTO_PATH"
                }
            }
        ]).toArray();

        const template = await fs.readFile(TEMPLATE_PATH, 'utf-8');
        await fs.ensureDir(HTML_OUTPUT_DIR);

        console.log(`📂 HTML 빌드 시작 (Join 완료): 총 ${membersWithPolicy.length}명`);

        for (const member of membersWithPolicy) {
            let html = template;

            // 3. SEO 및 프로필 데이터 치환
            html = html
                .replace(/{{MEMBER_NAME}}/g, member.name || "")
                .replace(/{{MEMBER_ID}}/g, member.naas_cd || "")
                .replace(/{{PARTY_NAME}}/g, member.party_name || "무소속")
                .replace(/{{REGION_NAME}}/g, member.region_name || "비례대표")
                .replace(/{{PHOTO_PATH}}/g, "/"+member.photo_path || "default.png")
                .replace(/{{ACHIEVEMENT_RATE}}/g, member.archivement_rate || 0)
                .replace(/{{AI_SUMMARY}}/g, member.ai_summary || "의정 활동 분석 중입니다.");

            await fs.writeFile(path.join(HTML_OUTPUT_DIR, `${member.name}.html`), html);
        }

        console.log(`✨ 빌드 완료: ${HTML_OUTPUT_DIR} 폴더를 확인하세요.`);

    } catch (err) {
        console.error("❌ Join 빌드 중 오류:", err);
    } finally {
        await client.close();
    }
}

buildHtmlWithJoin();