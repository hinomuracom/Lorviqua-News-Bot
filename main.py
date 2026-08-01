import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import urllib.request
import urllib.parse
import json
from datetime import datetime
import google.generativeai as genai

# ==========================================
# 1. 환경 변수 로드
# ==========================================
# 기본 검색 키워드: '로비큐아 OR 롤라티닙'
KEYWORD = os.getenv("SEARCH_KEYWORD", "로비큐아 OR 롤라티닙")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PW = os.getenv("SENDER_PW")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")


# ==========================================
# 2. 네이버 뉴스 API 수집 함수
# ==========================================
def fetch_news(keyword):
    """
    네이버 뉴스 API를 통해 최신 뉴스 10건을 수집합니다.
    """
    encText = urllib.parse.quote(keyword)
    url = f"https://openapi.naver.com/v1/search/news.json?query={encText}&display=10&sort=date"
    
    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", NAVER_CLIENT_ID)
    request.add_header("X-Naver-Client-Secret", NAVER_CLIENT_SECRET)
    
    try:
        response = urllib.request.urlopen(request)
        rescode = response.getcode()
        if rescode == 200:
            data = json.loads(response.read().decode('utf-8'))
            return data.get('items', [])
        else:
            print(f"네이버 API 호출 실패 (응답 코드: {rescode})")
            return []
    except Exception as e:
        print(f"뉴스 수집 중 오류 발생: {e}")
        return []


# ==========================================
# 3. Gemini AI 로비큐아 맞춤 요약 함수
# ==========================================
def summarize_news(items):
    """
    제약/의학 전문 프롬프트를 사용하여 수집된 뉴스를 요약합니다.
    """
    genai.configure(api_key=GEMINI_API_KEY)
    # Gemini 1.5 Flash 모델 사용
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # 수집된 뉴스 데이터 정제 및 컨텍스트 생성
    context = ""
    for idx, item in enumerate(items, 1):
        # HTML 강조 태그 및 특수문자 정제
        title = item['title'].replace('<b>', '').replace('</b>', '').replace('&quot;', '"').replace('&amp;', '&')
        desc = item['description'].replace('<b>', '').replace('</b>', '').replace('&quot;', '"').replace('&amp;', '&')
        link = item.get('originallink') or item.get('link')
        pub_date = item.get('pubDate', '')
        
        context += f"[{idx}] 제목: {title}\n"
        context += f"    발행일: {pub_date}\n"
        context += f"    요약문: {desc}\n"
        context += f"    원문 링크: {link}\n\n"

    # 로비큐아(롤라티닙) 맞춤형 AI 프롬프트
    prompt = f"""
    당신은 제약·바이오 및 항암제 전문 분석가입니다. 
    오늘 수집된 '{KEYWORD}' (ALK 양성 비소세포폐암 표적치료제 로비큐아/롤라티닙) 관련 뉴스 및 연구 동향을 바탕으로 일일 리포트를 작성해 주세요.

    [뉴스 목록]
    {context}

    [작성 가이드라인]
    1. **오늘의 핵심 동향 요약 (3~4줄)**:
       - 오늘 수집된 주요 이슈(건강보험 급여/허가, 임상시험 데이터 발표, 학회 소식, 처방 동향 등)를 명확하고 전문성 있게 요약해 주세요.
    
    2. **주요 소식 상세 분석 (분류별 정리)**:
       - 각 뉴스의 핵심 내용을 분야별(예: [급여/제도], [임상/연구], [시장/동향] 등)로 분류하여 정리해 주세요.
       - 소식 끝에 해당 뉴스의 원문 링크를 반드시 포함해 주세요.

    3. **핵심 참고 사항 및 시사점**:
       - 의료진, 환자, 또는 관련 산업 종사자 관점에서 유의깊게 봐야 할 시사점이나 핵심 포인트를 간략히 적어주세요.

    * 읽기 쉽도록 단락 구분 및 글머리 기호(•, -)를 활용해 주세요.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Gemini 요약 생성 중 오류 발생: {e}")
        return None


# ==========================================
# 4. 이메일 전송 함수 (Gmail SMTP)
# ==========================================
def send_email(subject, body):
    """
    Gmail SMTP 서비스를 이용해 결과 요약 메일을 발송합니다.
    """
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, SENDER_PW)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        print("이메일 발송이 성공적으로 완료되었습니다.")
    except Exception as e:
        print(f"이메일 발송 오류: {e}")


# ==========================================
# 5. 메인 실행부
# ==========================================
if __name__ == "__main__":
    print("=== 로비큐아 AI 뉴스 요약 시스템 실행 ===")
    print(f"검색 키워드: {KEYWORD}")
    
    # 1. 뉴스 데이터 수집
    news_items = fetch_news(KEYWORD)
    
    if not news_items:
        print("오늘 수집된 뉴스가 없습니다. 메일 발송을 취소합니다.")
    else:
        print(f"총 {len(news_items)}건의 뉴스를 수집했습니다.")
        
        # 2. Gemini AI 요약 생성
        print("Gemini AI 요약 생성 중...")
        summary_result = summarize_news(news_items)
        
        if summary_result:
            # 3. 메일 제목 생성 및 발송
            today_str = datetime.now().strftime('%Y-%m-%d')
            email_subject = f"[{today_str}] '로비큐아(Lorviqua)' AI 뉴스 및 임상동향 리포트"
            
            print("이메일 발송 중...")
            send_email(email_subject, summary_result)
        else:
            print("AI 요약 생성 실패로 메일을 발송하지 못했습니다.")