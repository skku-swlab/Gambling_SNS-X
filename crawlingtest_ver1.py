from playwright.sync_api import sync_playwright
import pandas as pd
import time
from datetime import datetime
import json
import random
from rich.console import Console
from pathlib import Path

console = Console()

class XCookieScraper:
    def __init__(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-features=site-per-process',
                '--no-sandbox',
            ]
        )
        
        # 브라우저 컨텍스트 설정
        self.context = self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        )
        self.page = self.context.new_page()
        
    def save_cookies(self, cookie_file='twitter_cookies.json'):
        """현재 세션의 쿠키를 파일로 저장"""
        cookies = self.context.cookies()
        Path(cookie_file).write_text(json.dumps(cookies))
        console.print(f"[green]쿠키가 {cookie_file}에 저장되었습니다.[/green]")
        
    def load_cookies(self, cookie_file='twitter_cookies.json'):
        """저장된 쿠키 파일을 불러와서 적용"""
        try:
            cookies = json.loads(Path(cookie_file).read_text())
            self.context.add_cookies(cookies)
            console.print("[green]쿠키를 성공적으로 불러왔습니다.[/green]")
            return True
        except Exception as e:
            console.print(f"[yellow]쿠키 로드 실패: {str(e)}[/yellow]")
            return False

    def manual_login(self):
        """수동 로그인 후 쿠키 저장"""
        console.print("[bold cyan]수동 로그인 절차 시작[/bold cyan]")
        console.print("1. 브라우저에서 X에 직접 로그인해주세요.")
        console.print("2. 로그인이 완료되면 아무 키나 눌러주세요.")
        
        # X 로그인 페이지로 이동
        self.page.goto('https://twitter.com/i/flow/login')
        
        # 사용자가 수동으로 로그인할 때까지 대기
        input("로그인이 완료되면 Enter를 눌러주세요...")
        
        # 로그인 상태 확인
        if self.check_login():
            console.print("[green]로그인 확인됨! 쿠키를 저장합니다.[/green]")
            self.save_cookies()
            return True
        else:
            console.print("[red]로그인 상태를 확인할 수 없습니다.[/red]")
            return False

    def check_login(self):
        """로그인 상태 확인"""
        try:
            self.page.goto('https://twitter.com/home')
            time.sleep(2)
            return 'login' not in self.page.url
        except Exception:
            return False

    def search_tweets(self, query, max_tweets=100):
        """트윗 검색 및 수집"""
        if not self.check_login():
            console.print("[yellow]로그인되지 않은 상태입니다. 먼저 로그인이 필요합니다.[/yellow]")
            return []

        tweets = []
        search_url = f'https://twitter.com/search?q={query}&f=live'
        self.page.goto(search_url)
        time.sleep(2)

        while len(tweets) < max_tweets:
            tweet_elements = self.page.query_selector_all('article[data-testid="tweet"]')
            
            for tweet in tweet_elements:
                if len(tweets) >= max_tweets:
                    break
                    
                try:
                    tweet_data = self._extract_tweet_data(tweet)
                    if tweet_data and not any(t['id'] == tweet_data['id'] for t in tweets):
                        tweets.append(tweet_data)
                        console.print(f"[green]트윗 수집: {len(tweets)}/{max_tweets}[/green]")
                except Exception as e:
                    console.print(f"[yellow]트윗 추출 실패: {str(e)}[/yellow]")
            
            # 부드러운 스크롤
            self._smooth_scroll()
            time.sleep(random.uniform(1, 3))
            
        return tweets

    def _extract_tweet_data(self, tweet_element):
        """트윗 데이터 추출"""
        try:
            # 트윗 ID 추출
            link = tweet_element.query_selector('a[href*="/status/"]')
            tweet_id = link.get_attribute('href').split('/status/')[-1] if link else None
            
            # 텍스트 내용
            text = tweet_element.query_selector('[data-testid="tweetText"]')
            text_content = text.inner_text() if text else ""
            
            # 사용자 정보
            user_element = tweet_element.query_selector('[data-testid="User-Name"]')
            user_info = user_element.inner_text().split('\n') if user_element else []
            user_name = user_info[0] if user_info else ""
            user_handle = user_info[1] if len(user_info) > 1 else ""
            
            return {
                'id': tweet_id,
                'text': text_content,
                'user_name': user_name,
                'user_handle': user_handle,
                'collected_at': datetime.now().isoformat()
            }
        except Exception as e:
            console.print(f"[yellow]데이터 추출 중 오류: {str(e)}[/yellow]")
            return None

    def _smooth_scroll(self, distance=300, steps=10):
        """부드러운 스크롤 구현"""
        for _ in range(steps):
            self.page.evaluate(f'window.scrollBy(0, {distance/steps})')
            time.sleep(0.05)

    def close(self):
        """브라우저 종료"""
        self.context.close()
        self.browser.close()
        self.playwright.stop()

def main():
    scraper = XCookieScraper()
    console.print("[bold cyan]X 스크래퍼 시작[/bold cyan]")
    
    try:
        # 저장된 쿠키가 있다면 불러오기 시도
        if not scraper.load_cookies() or not scraper.check_login():
            # 쿠키 로드 실패 또는 로그인 상태가 아닌 경우 수동 로그인 진행
            if not scraper.manual_login():
                console.print("[red]로그인에 실패했습니다.[/red]")
                return
        
        # 검색 실행
        search_query = input("검색어를 입력하세요: ")
        max_tweets = int(input("수집할 트윗 수를 입력하세요: "))
        
        tweets = scraper.search_tweets(search_query, max_tweets)
        
        # 결과 저장
        if tweets:
            df = pd.DataFrame(tweets)
            filename = f"tweets_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            console.print(f"[bold green]결과가 {filename}에 저장되었습니다![/bold green]")
        
    except Exception as e:
        console.print(f"[bold red]에러 발생: {str(e)}[/bold red]")
    finally:
        scraper.close()

if __name__ == "__main__":
    main()