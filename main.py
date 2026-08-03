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
KEYWORD = os.getenv("SEARCH_KEYWORD", "로비큐아 OR ALK 돌연변이")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PW = os.getenv("SENDER_PW")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")


# ==========================================
# 2. 네이버 뉴스 및 블로그 통합 수집 함수 (수정됨)
# ==========================================
def fetch_news(keyword):
    """
    네이버 뉴스 5건 + 블로그 5건을 수집하여 하나의 리스트로 통합합니다.
    """
    encText = urllib.parse.quote(keyword)
    
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    
    combined_items = []

    try:
        # 1) 뉴스 5건 수집
        news_url = f"https://openapi.naver.com/v1/search/news.json?query={encText}&display=5&sort=date"
        req_news = urllib.request.Request(news_url, headers=headers)
        res_news = urllib.request.urlopen(req_news)
        if res_news.getcode() == 200:
            news_data = json.loads(res_news.read().decode('utf-8'))
            for item in news_data.get('items', []):
                item['type'] = '뉴스'
                combined_items.append(item)

        # 2) 블로그 5건 수집
        blog_url = f"https://openapi.naver.com/v1/search/blog.json?query={encText}&display=5&sort=date"
        req_blog = urllib.request.Request(blog_url, headers=headers)
        res_blog = urllib.request.urlopen(req_blog)
        if res_blog.getcode() == 200:
            blog_data = json.loads(res_blog.read().decode('utf-8'))
            for item in blog_data.get('items', []):
                item['type'] = '블로그'
                # 블로그 API의 링크 키값(link) 처리
                item['originallink'] = item.get('link')
                combined_items.append(item)

        return combined_items

    except Exception as e:
        print(f"데이터 수집 중 오류 발생: {e}")
        return []


# ==========================================
# 3. Gemini AI 맞춤 요약 함수 (뉴스+블로그 대응)
# ==========================================
def summarize_news(items):
    """
    뉴스 및 블로그 수집 데이터를 바탕으로 AI 요약을 생성합니다.
    """
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    context = ""
    for idx, item in enumerate(items, 1):
        item_type = item.get('type', '소식')
        title = item['title'].replace('<b>', '').replace('</b>', '').replace('&quot;', '"').replace('&amp;', '&')
        desc = item['description'].replace('<b>', '').replace('</b>', '').replace('&quot;', '"').replace('&amp;', '&')
        link = item.get('originallink') or item.get('link')
        pub_date = item.get('pubDate', '')
        
        context += f"[{idx}] [{item_type}] 제목: {title}\n"
        context += f"    발행일: {pub_date}\n"
        context += f"    요약문: {desc}\n"
        context += f"    원문 링크: {link}\n\n"

    prompt = f"""
    당신은 제약·바이오 및 항암제 전문 분석가입니다. 
    오늘 수집된 '{KEYWORD}' (ALK 양성 비소세포폐암 표적치료제 로비큐아/롤라티닙) 관련 뉴스 및 블로그 포스팅 동향을 바탕으로 일일 리포트를 작성해 주세요.

    [수집된 데이터 목록]
    {context}

    [작성 가이드라인]
    1. **오늘의 핵심 동향 요약 (3~4줄)**:
       - 오늘 수집된 뉴스(급여/허가, 임상 소식 등)와 블로그(환자/의료진 후기, 정보 공유 등)의 전체적인 주요 이슈를 요약해 주세요.
    
    2. **주요 소식 및 포스팅 분석**:
       - 뉴스 기사의 주요 소식과 블로그 포스팅의 주요 내용을 구분하거나 분류(예: [언론 보도], [블로그/환자 동향] 등)하여 핵심 내용을 1~2문장으로 정리해 주세요.
       - 소식 끝에 해당 원문 링크를 반드시 함께 포함해 주세요.

    3. **핵심 참고 사항 및 시사점**:
       - 의료진, 환자, 또는 관련 산업 종사자 관점에서 유의깊게 봐야 할 시사점이나 포인트를 적어주세요.

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
    print("=== 로비큐아 AI 뉴스+블로그 요약 시스템 실행 ===")
    print(f"검색 키워드: {KEYWORD}")
    
    # 1. 데이터 수집 (뉴스 + 블로그)
    items = fetch_news(KEYWORD)
    
    if not items:
        print("오늘 수집된 뉴스 및 블로그 데이터가 없습니다. 메일 발송을 취소합니다.")
    else:
        print(f"총 {len(items)}건의 데이터(뉴스+블로그)를 수집했습니다.")
        
        # 2. Gemini AI 요약 생성
        print("Gemini AI 요약 생성 중...")
        summary_result = summarize_news(items)
        
        if summary_result:
            # 3. 메일 제목 생성 및 발송
            today_str = datetime.now().strftime('%Y-%m-%d')
            email_subject = f"[{today_str}] '로비큐아(Lorviqua)' AI 뉴스 & 블로그 동향 리포트"
            
            print("이메일 발송 중...")
            send_email(email_subject, summary_result)
        else:
            print("AI 요약 생성 실패로 메일을 발송하지 못했습니다.")
