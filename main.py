# app.py
import streamlit as st
from newspaper import Article
from transformers import pipeline
import requests
from bs4 import BeautifulSoup
import nltk
import torch

# ********** FIX: Set page config FIRST **********
st.set_page_config(
    page_title="Advanced Article Summarizer",
    page_icon="📰",
    layout="centered",
    initial_sidebar_state="expanded"
)
# Disable problematic watchers early
from streamlit.watcher import local_sources_watcher
local_sources_watcher._cached_blacklist = lambda: ["torch", "transformers"]
# Initialize summarization pipeline
@st.cache_resource
def load_summarizer():
    # Set NLTK data path explicitly
    nltk.data.path.append("./nltk_data")

    # Download required resources
    try:
        nltk.data.find('tokenizers/punkt_tab')
    except LookupError:
        nltk.download('punkt_tab', download_dir="./nltk_data", quiet=True)

    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt', download_dir="./nltk_data", quiet=True)

    return pipeline("summarization", model="facebook/bart-large-cnn")

summarizer = load_summarizer()

# Web scraping function with fallback
def extract_article_content(url):
    try:
        # Set custom headers to mimic a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.google.com/',
            'DNT': '1',
            'Connection': 'keep-alive'
        }

        # Try using newspaper3k with custom headers
        article = Article(url, headers=headers)
        article.download()
        article.parse()
        article.nlp()

        if len(article.text) > 500:
            return {
                'text': article.text,
                'title': article.title,
                'keywords': article.keywords,
                'summary': article.summary,
                'images': article.images
            }

        # Fallback with requests + BeautifulSoup
        session = requests.Session()
        session.mount('https://', requests.adapters.HTTPAdapter(max_retries=3))

        response = session.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Remove unnecessary elements
        for element in soup(['script', 'style', 'nav', 'footer', 'aside', 'figure']):
            element.decompose()

        # Extract main content
        main_content = soup.find('article') or soup.find('main') or soup.body
        paragraphs = main_content.find_all('p')
        text = '\n'.join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])

        return {
            'text': text,
            'title': soup.title.string if soup.title else "No Title Found"
        }

    except Exception as e:
        st.error(f"Error extracting content: {str(e)}")
        return None

# Streamlit UI
st.title("📰 Advanced Article Summarizer")
st.markdown("Paste text or a URL to generate a summary (supports 300+ news sites)")

# Session state to preserve inputs
if 'input_content' not in st.session_state:
    st.session_state.input_content = ""
if 'url' not in st.session_state:
    st.session_state.url = ""

input_method = st.radio("Input method:", ("Text", "URL"))

if input_method == "Text":
    st.session_state.input_content = st.text_area(
        "Paste your article text here:",
        height=200,
        value=st.session_state.input_content
    )
else:
    st.session_state.url = st.text_input(
        "Enter article URL:",
        value=st.session_state.url
    )
    if st.session_state.url:
        with st.spinner("📡 Downloading and parsing article..."):
            article_data = extract_article_content(st.session_state.url)
            if article_data:
                st.session_state.input_content = article_data['text']
                st.success(f"✅ Successfully extracted: {article_data.get('title', 'Untitled Article')}")

if st.session_state.input_content:
    st.markdown("---")
    st.subheader("Article Preview")
    st.caption(f"Character count: {len(st.session_state.input_content)}")

    # Configuration sidebar
    with st.sidebar:
        st.header("Settings")
        max_length = st.slider("Max summary length", 100, 600, 300)
        min_length = st.slider("Min summary length", 30, 150, 50)
        do_sample = st.checkbox("Enable sampling", False)
        chunk_size = st.number_input("Chunk size (characters)", 500, 2000, 1024)

    # Generate summary
    if st.button("Generate Summary"):
        with st.spinner("🤖 Analyzing content and generating summary..."):
            try:
                # Split long text into chunks
                chunks = [
                    st.session_state.input_content[i:i+chunk_size]
                    for i in range(0, len(st.session_state.input_content), chunk_size)
                ]

                summaries = []
                for chunk in chunks:
                    summary = summarizer(
                        chunk,
                        max_length=max_length,
                        min_length=min_length,
                        do_sample=do_sample,
                        truncation=True
                    )
                    summaries.append(summary[0]['summary_text'])

                full_summary = ' '.join(summaries)

                st.subheader("Generated Summary")
                st.success(full_summary)

                # Show original text in expander
                with st.expander("View Original Text"):
                    st.write(st.session_state.input_content)

            except Exception as e:
                st.error(f"Error generating summary: {str(e)}")

# Add footer
st.markdown("---")
st.markdown("Built with ♥ using [Streamlit](https://streamlit.io/), [Hugging Face](https://huggingface.co/), and [newspaper3k](https://newspaper.readthedocs.io/)")