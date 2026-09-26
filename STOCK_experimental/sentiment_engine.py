"""
sentiment_engine.py — SentimentEngine class with Hierarchical Confidence-Gated Fusion.

Sources (per market):
  Indian stocks : MoneyControl headlines, Economic Times markets via BeautifulSoup
  Foreign stocks: NewsAPI (free tier), Yahoo Finance RSS
  Global        : Reddit (r/investing, r/IndiaInvestments) via PRAW
  Fallback      : yfinance built-in news

Processing:
  1. Clean / preprocess headline text (strip HTML, stopwords)
  2. Score with VADER (fast, always available)
  3. Score with FinBERT (ProsusAI/finbert) — now returns (score, confidence)
  4. Hierarchical Confidence-Gated Fusion (Rank 5):
       - High FinBERT confidence (>= 0.80) => FinBERT overrides VADER entirely
       - Low  FinBERT confidence (<  0.55) => Fall back to VADER only
       - Mid  FinBERT confidence           => Proportional blend (confidence-weighted)
  5. Recency-weighted exponential moving average across headlines
     (newer headlines are weighted more heavily than older ones)
  6. Rolling 3-day & 7-day mean sentiment, momentum

Output features:
  daily_sentiment_score, sentiment_3d_rolling, sentiment_7d_rolling,
  sentiment_momentum, news_volume, finbert_confidence
"""

import re

import warnings
warnings.filterwarnings("ignore")

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# VADER — always available
import nltk
nltk.download("vader_lexicon", quiet=True)
nltk.download("stopwords", quiet=True)
from nltk.sentiment import SentimentIntensityAnalyzer
from nltk.corpus import stopwords

# Web scraping
import requests
from bs4 import BeautifulSoup

# yfinance for fallback news
import yfinance as yf

from config import CONFIG, SENTIMENT_FEATURES

logger = logging.getLogger(__name__)

# ── Optional heavy imports (loaded lazily) ────────────────────────────────────
_finbert_pipeline = None
_praw_reddit      = None


def _load_finbert():
    """Lazy-load FinBERT pipeline. ~400 MB download on first run."""
    global _finbert_pipeline
    if _finbert_pipeline is not None:
        return _finbert_pipeline
    try:
        from transformers import (
            AutoTokenizer,
            AutoModelForSequenceClassification,
            pipeline,
        )
        import torch

        model_name = "ProsusAI/finbert"
        device = 0 if torch.cuda.is_available() else -1
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model     = AutoModelForSequenceClassification.from_pretrained(model_name)
        _finbert_pipeline = pipeline(
            "sentiment-analysis",
            model=model,
            tokenizer=tokenizer,
            device=device,
            truncation=True,
            max_length=512,
        )
        logger.info(f"FinBERT loaded (device={'cuda' if device==0 else 'cpu'})")
        return _finbert_pipeline
    except Exception as e:
        logger.warning(f"FinBERT unavailable: {e}. Using VADER only.")
        return None


def _load_reddit():
    """Lazy-load Reddit PRAW client."""
    global _praw_reddit
    if _praw_reddit is not None:
        return _praw_reddit

    cid = CONFIG["reddit_client_id"]
    csec = CONFIG["reddit_client_secret"]
    ua   = CONFIG["reddit_user_agent"]
    if not cid or not csec:
        return None
    try:
        import praw
        _praw_reddit = praw.Reddit(
            client_id=cid, client_secret=csec,
            user_agent=ua,
        )
        logger.info("Reddit PRAW client initialised")
        return _praw_reddit
    except Exception as e:
        logger.warning(f"Reddit PRAW unavailable: {e}")
        return None


class SentimentEngine:
    """
    Fetches, scores, and aggregates news sentiment for a given ticker.
    Gracefully degrades: if no API keys → yfinance news + VADER only.
    """

    def __init__(self):
        self.vader = SentimentIntensityAnalyzer()
        self.stop_words = set(stopwords.words("english"))
        self.finbert = None
        self.reddit  = None

        # Load FinBERT if enabled
        if CONFIG["use_finbert"]:
            self.finbert = _load_finbert()

        # Load Reddit
        self.reddit = _load_reddit()

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        })

    # ══════════════════════════════════════════════════════════════════════
    #  NEWS FETCHING — per market
    # ══════════════════════════════════════════════════════════════════════

    def _fetch_yfinance_news(self, ticker: str) -> list:
        """Fallback: get headlines from yfinance Ticker.news."""
        try:
            news = yf.Ticker(ticker).news or []
            headlines = []
            for art in news[:CONFIG["max_headlines"]]:
                title = art.get("title", "")
                pub   = art.get("providerPublishTime", None)
                link  = art.get("link", "")
                if title:
                    dt = datetime.utcfromtimestamp(pub) if pub else datetime.utcnow()
                    headlines.append({"title": title, "date": dt, "link": link})
            return headlines
        except Exception as e:
            logger.warning(f"yfinance news failed for {ticker}: {e}")
            return []

    def _fetch_moneycontrol(self, ticker: str) -> list:
        """Scrape MoneyControl headlines for Indian stocks."""
        # Extract company name from ticker (e.g. RELIANCE.NS → reliance)
        company = ticker.split(".")[0].lower()
        url = f"https://www.moneycontrol.com/news/tags/{company}.html"
        headlines = []
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return headlines
            soup = BeautifulSoup(resp.text, "lxml")
            # MoneyControl news list items
            for item in soup.select("li.clearfix")[:20]:
                title_tag = item.select_one("h2 a") or item.select_one("a")
                if title_tag and title_tag.text.strip():
                    link = title_tag.get("href", "")
                    if link and not link.startswith("http"):
                        link = "https://www.moneycontrol.com" + link
                    headlines.append({
                        "title": title_tag.text.strip(),
                        "date": datetime.utcnow(),
                        "link": link
                    })
            logger.info(f"  MoneyControl: {len(headlines)} headlines for {ticker}")
        except Exception as e:
            logger.debug(f"MoneyControl scrape failed: {e}")
        return headlines

    def _fetch_economic_times(self, ticker: str) -> list:
        """Scrape Economic Times markets section for Indian stocks."""
        company = ticker.split(".")[0].lower()
        url = f"https://economictimes.indiatimes.com/topic/{company}"
        headlines = []
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return headlines
            soup = BeautifulSoup(resp.text, "lxml")
            for item in soup.select("div.clr a, div.eachStory a")[:20]:
                text = item.text.strip()
                if len(text) > 15:  # filter out navigation links
                    link = item.get("href", "")
                    if link and not link.startswith("http"):
                        link = "https://economictimes.indiatimes.com" + link
                    headlines.append({"title": text, "date": datetime.utcnow(), "link": link})
            logger.info(f"  Economic Times: {len(headlines)} headlines for {ticker}")
        except Exception as e:
            logger.debug(f"ET scrape failed: {e}")
        return headlines

    def _fetch_newsapi(self, ticker: str) -> list:
        """Fetch headlines from NewsAPI (free tier, 100 req/day)."""
        api_key = CONFIG["news_api_key"]
        if not api_key:
            return []

        company = ticker.split(".")[0]
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": f'"{company}" stock',
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": min(CONFIG["max_headlines"], 50),
            "apiKey": api_key,
        }
        headlines = []
        try:
            resp = self.session.get(url, params=params, timeout=10)
            data = resp.json()
            for art in data.get("articles", []):
                title = art.get("title", "")
                pub   = art.get("publishedAt", "")
                link  = art.get("url", "")
                if title and title != "[Removed]":
                    try:
                        dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                    except Exception:
                        dt = datetime.utcnow()
                    headlines.append({"title": title, "date": dt, "link": link})
            logger.info(f"  NewsAPI: {len(headlines)} headlines for {ticker}")
        except Exception as e:
            logger.debug(f"NewsAPI failed: {e}")
        return headlines

    def _fetch_yahoo_rss(self, ticker: str) -> list:
        """Fetch from Yahoo Finance RSS feed."""
        url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
        headlines = []
        try:
            resp = self.session.get(url, timeout=10)
            soup = BeautifulSoup(resp.text, "xml")
            for item in soup.find_all("item")[:20]:
                title = item.find("title")
                link_tag = item.find("link")
                link = link_tag.text if link_tag else ""
                if title and title.text.strip():
                    headlines.append({
                        "title": title.text.strip(),
                        "date": datetime.utcnow(),
                        "link": link
                    })
            logger.info(f"  Yahoo RSS: {len(headlines)} headlines for {ticker}")
        except Exception as e:
            logger.debug(f"Yahoo RSS failed: {e}")
        return headlines

    def _fetch_reddit(self, ticker: str, market: str) -> list:
        """Fetch recent posts from relevant subreddits via PRAW."""
        if self.reddit is None:
            return []

        subreddits = ["investing", "stocks"]
        if market in ("NSE", "BSE"):
            subreddits.append("IndiaInvestments")

        company = ticker.split(".")[0]
        headlines = []
        try:
            for sub_name in subreddits:
                sub = self.reddit.subreddit(sub_name)
                for post in sub.search(company, sort="new", time_filter="week", limit=10):
                    headlines.append({
                        "title": post.title,
                        "date": datetime.utcfromtimestamp(post.created_utc),
                        "link": f"https://reddit.com{post.permalink}" if hasattr(post, "permalink") else ""
                    })
            logger.info(f"  Reddit: {len(headlines)} posts for {ticker}")
        except Exception as e:
            logger.debug(f"Reddit fetch failed: {e}")
        return headlines

    # ══════════════════════════════════════════════════════════════════════
    #  TEXT PREPROCESSING
    # ══════════════════════════════════════════════════════════════════════

    def _clean_text(self, text: str) -> str:
        """Remove HTML tags, URLs, special chars, and stopwords."""
        # Strip HTML
        text = BeautifulSoup(text, "html.parser").get_text()
        # Remove URLs
        text = re.sub(r"http\S+|www\.\S+", "", text)
        # Remove special characters but keep spaces and basic punctuation
        text = re.sub(r"[^a-zA-Z0-9\s.,!?'-]", " ", text)
        # Remove extra whitespace
        text = " ".join(text.split())
        return text.strip()

    def _is_valid_headline(self, title: str) -> bool:
        """Filter out common login/navigation/advertisement/noise text."""
        title_lower = title.lower()
        noise_keywords = [
            "login", "log in", "log-in", "hello, login", "hello login", "sign in", "sign-in", "register",
            "subscribe", "feedback", "privacy policy", "terms of service", "cookie", "contact us",
            "about us", "careers", "advertising", "sitemap", "help", "faq", "hello, user", "my account"
        ]
        for keyword in noise_keywords:
            if keyword in title_lower:
                return False
        return True

    # ══════════════════════════════════════════════════════════════════════
    #  SCORING
    # ══════════════════════════════════════════════════════════════════════

    def _score_vader(self, text: str) -> float:
        """VADER compound score in [-1, 1]."""
        return self.vader.polarity_scores(text)["compound"]

    def _score_finbert(self, text: str) -> tuple:
        """
        FinBERT sentiment score with confidence.

        Returns:
            (score, confidence) where:
              score      : float in [-1, 1] (positive=+1, negative=-1, neutral=0)
              confidence : float in [0, 1] — the raw logit probability for
                           the predicted class. This is used by the confidence
                           gate to decide how much to trust FinBERT vs VADER.
        """
        if self.finbert is None:
            return 0.0, 0.0
        try:
            result     = self.finbert(text[:512])[0]
            label      = result["label"].lower()
            confidence = float(result["score"])    # logit probability [0, 1]
            if label == "positive":
                return confidence, confidence
            elif label == "negative":
                return -confidence, confidence
            else:
                return 0.0, confidence
        except Exception:
            return 0.0, 0.0

    def _aggregate_score(
        self,
        vader_score: float,
        finbert_score: float,
        finbert_confidence: float,
        high_conf_threshold: float = 0.80,
        low_conf_threshold:  float = 0.55,
    ) -> float:
        """
        Hierarchical Confidence-Gated Fusion of VADER and FinBERT.

        This replaces the previous fixed weighted average with a principled
        three-tier confidence gate:

          Tier 1 (High confidence: finbert_conf >= high_conf_threshold):
            FinBERT completely overrides VADER. When FinBERT is very sure
            (e.g., 0.95 confidence for 'positive'), its domain-specific
            financial language understanding is more trustworthy than VADER's
            general lexicon.

          Tier 2 (Low confidence: finbert_conf < low_conf_threshold):
            FinBERT is uncertain (score near the decision boundary). In this
            case we completely discard the FinBERT score and rely solely on
            VADER to prevent noisy signals from hurting accuracy.

          Tier 3 (Mid confidence: low_conf_threshold <= conf < high_conf_threshold):
            Proportional blend where the blend weight is proportional to how
            confident FinBERT is within the [low, high] range. A confidence
            of 0.55 => mostly VADER; a confidence of 0.79 => mostly FinBERT.

        Args:
            vader_score:          VADER compound score in [-1, 1].
            finbert_score:        FinBERT signed score in [-1, 1].
            finbert_confidence:   FinBERT's logit probability for its prediction.
            high_conf_threshold:  Above this, FinBERT fully overrides VADER.
            low_conf_threshold:   Below this, VADER fully overrides FinBERT.

        Returns:
            float in [-1, 1] — the fused sentiment score.
        """
        if self.finbert is None or finbert_confidence == 0.0:
            return vader_score   # VADER-only fallback

        if finbert_confidence >= high_conf_threshold:
            # Tier 1: FinBERT is dominant — financial domain expert
            return finbert_score

        elif finbert_confidence < low_conf_threshold:
            # Tier 2: FinBERT uncertain — VADER is more reliable
            return vader_score

        else:
            # Tier 3: Proportional blend in [low, high] range
            # blend_w=0 at low_conf (pure VADER), blend_w=1 at high_conf (pure FinBERT)
            blend_w = (finbert_confidence - low_conf_threshold) / (
                high_conf_threshold - low_conf_threshold + 1e-9
            )
            return (1.0 - blend_w) * vader_score + blend_w * finbert_score


    # ══════════════════════════════════════════════════════════════════════
    #  PUBLIC API
    # ══════════════════════════════════════════════════════════════════════

    def fetch_and_score(self, ticker: str, market: str) -> dict:
        """
        Fetch all available news for a ticker, score each headline,
        and return aggregated sentiment features.

        Returns dict with keys:
          daily_sentiment_score, sentiment_3d_rolling, sentiment_7d_rolling,
          sentiment_momentum, news_volume, top_headline, sentiment_label
        """
        # ── 1. Collect headlines from all sources ─────────────────────────
        all_headlines = []

        # Always try yfinance news (universal fallback)
        all_headlines.extend(self._fetch_yfinance_news(ticker))

        # Market-specific sources
        if market in ("NSE", "BSE"):
            all_headlines.extend(self._fetch_moneycontrol(ticker))
            all_headlines.extend(self._fetch_economic_times(ticker))
        else:
            all_headlines.extend(self._fetch_newsapi(ticker))
            all_headlines.extend(self._fetch_yahoo_rss(ticker))

        # Reddit (global)
        all_headlines.extend(self._fetch_reddit(ticker, market))

        # Deduplicate and filter by title validity
        seen = set()
        unique = []
        for h in all_headlines:
            title_text = h["title"].strip()
            if not self._is_valid_headline(title_text):
                continue
            key = title_text.lower()[:80]
            if key not in seen:
                seen.add(key)
                unique.append(h)
        all_headlines = unique[:CONFIG["max_headlines"]]

        # ── 2. Score each headline with recency-based EMA weighting ──────
        # Recency: sort by date descending. Assign exponentially decaying
        # weights so that the most recent headlines matter most.
        # EMA decay: weight_i = alpha^i where alpha=0.85, i=0 is newest.
        EMA_ALPHA = 0.85
        scores         = []
        weights        = []
        confidences    = []

        # Sort by date descending (newest first) for EMA weight assignment
        all_headlines_sorted = sorted(
            all_headlines, key=lambda h: h.get("date", datetime.utcnow()), reverse=True
        )

        for i, h in enumerate(all_headlines_sorted):
            clean = self._clean_text(h["title"])
            if len(clean) < 10:
                continue
            v = self._score_vader(clean)
            if self.finbert:
                f, conf = self._score_finbert(clean)
            else:
                f, conf = 0.0, 0.0
            agg = self._aggregate_score(v, f, conf)
            w   = EMA_ALPHA ** i          # newer headline => higher weight
            scores.append(agg)
            weights.append(w)
            confidences.append(conf)

        # ── 3. Aggregate with EMA weights ──────────────────────────────────
        if not scores:
            return {
                "daily_sentiment_score": 0.0,
                "sentiment_3d_rolling":  0.0,
                "sentiment_7d_rolling":  0.0,
                "sentiment_momentum":    0.0,
                "news_volume":           0.0,
                "finbert_confidence":    0.0,
                "top_headline":          "no latest news on this",
                "top_link":              "",
                "sentiment_label":       "Neutral",
            }

        weights_arr   = np.array(weights, dtype=float)
        weights_arr  /= weights_arr.sum()    # normalize to sum=1
        daily_score   = float(np.dot(scores, weights_arr))
        mean_conf     = float(np.mean(confidences)) if confidences else 0.0
        news_vol      = min(len(scores) / 20.0, 1.0)  # normalise to [0, 1]

        # For rolling / momentum we need historical data, but since we
        # scrape only current headlines we store single-day values;
        # the rolling computation happens in get_historical_features().
        if daily_score > 0.15:
            label = "Bullish"
        elif daily_score < -0.15:
            label = "Bearish"
        else:
            label = "Neutral"

        top = all_headlines[0]["title"] if all_headlines else "no latest news on this"
        top_link = all_headlines[0].get("link", "") if all_headlines else ""

        return {
            "daily_sentiment_score": round(daily_score, 4),
            "sentiment_3d_rolling":  round(daily_score, 4),  # single-day proxy
            "sentiment_7d_rolling":  round(daily_score, 4),
            "sentiment_momentum":    0.0,
            "news_volume":           round(news_vol, 4),
            "finbert_confidence":    round(mean_conf, 4),
            "top_headline":          top,
            "top_link":              top_link,
            "sentiment_label":       label,
        }


    def get_historical_features(self, df: pd.DataFrame,
                                current_sentiment: dict) -> pd.DataFrame:
        """
        Add sentiment feature columns to a historical DataFrame.

        Since real-time scrapers only give us *current* sentiment, for
        historical backtest we simulate with a proxy: we use the broader 
        market index (^NSEI) return polarity as a macro sentiment proxy.
        This completely eliminates ticker-specific data leakage (predicting 
        price from price) while preserving macro fear/greed cycles.
        """
        # Fetch NIFTY50 data if not already cached
        if not hasattr(self, '_nifty_cache'):
            try:
                import yfinance as yf
                nifty = yf.download("^NSEI", start=df.index.min() - pd.Timedelta(days=30), 
                                    end=df.index.max() + pd.Timedelta(days=1), progress=False)
                self._nifty_cache = nifty["Close"]
            except Exception as e:
                logger.warning(f"Failed to fetch NIFTY for sentiment proxy: {e}")
                self._nifty_cache = pd.Series(1, index=df.index)  # flat fallback

        # Proxy: 5-day rolling return of the broader market index
        idx_ret5 = self._nifty_cache.pct_change(5).reindex(df.index, method='ffill')
        proxy = idx_ret5.rolling(5).mean() * 10  # scale to [-1, 1]-ish range
        proxy = proxy.clip(-1, 1)

        df["daily_sentiment_score"] = proxy.fillna(0)
        df["sentiment_3d_rolling"]  = df["daily_sentiment_score"].rolling(3).mean().fillna(0)
        df["sentiment_7d_rolling"]  = df["daily_sentiment_score"].rolling(7).mean().fillna(0)
        df["sentiment_momentum"]    = df["daily_sentiment_score"].diff().fillna(0)
        df["news_volume"]           = 0.5  # neutral default for historical

        # Override the most recent row with actual scraped sentiment
        if current_sentiment and len(df) > 0:
            last_idx = df.index[-1]
            df.loc[last_idx, "daily_sentiment_score"] = current_sentiment["daily_sentiment_score"]
            df.loc[last_idx, "sentiment_3d_rolling"]  = current_sentiment["sentiment_3d_rolling"]
            df.loc[last_idx, "sentiment_7d_rolling"]  = current_sentiment["sentiment_7d_rolling"]
            df.loc[last_idx, "sentiment_momentum"]    = current_sentiment["sentiment_momentum"]
            df.loc[last_idx, "news_volume"]           = current_sentiment["news_volume"]

        return df
