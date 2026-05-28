"""
Export des figures The North Face vers reports/figures/
Usage : /opt/anaconda3/bin/python src/export_figures.py
"""
import re
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from wordcloud import WordCloud
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

import spacy
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import DBSCAN
from sklearn.decomposition import TruncatedSVD
from sklearn.metrics.pairwise import cosine_similarity

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "reports" / "figures"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DATA = Path(__file__).resolve().parents[1] / "data" / "raw" / "sample-data.csv"

# ── Chargement ─────────────────────────────────────────────────────────────────
print("Chargement des données...")
df = pd.read_csv(DATA)

nlp = spacy.load('en_core_web_sm')

def clean_html(text):
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&[a-z]+;', ' ', text)
    text = re.sub(r'[^a-zA-Z\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def preprocess(text):
    doc = nlp(text.lower())
    tokens = [
        token.lemma_ for token in doc
        if not token.is_stop and not token.is_punct and len(token.lemma_) > 2
    ]
    return ' '.join(tokens)

print("Preprocessing NLP (peut prendre 1-2 min)...")
df['description_clean'] = df['description'].apply(clean_html)
df['description_processed'] = df['description_clean'].apply(preprocess)

vectorizer = TfidfVectorizer(max_features=500)
tfidf_matrix = vectorizer.fit_transform(df['description_processed'])
feature_names = vectorizer.get_feature_names_out()

# ── DBSCAN ─────────────────────────────────────────────────────────────────────
print("DBSCAN clustering...")
db = DBSCAN(eps=0.65, min_samples=3, metric='cosine')
df['cluster'] = db.fit_predict(tfidf_matrix)

n_clusters = len(set(df['cluster'])) - (1 if -1 in df['cluster'].values else 0)
n_noise    = (df['cluster'] == -1).sum()
print(f"  {n_clusters} clusters, {n_noise} outliers")

# ── LSA ────────────────────────────────────────────────────────────────────────
print("LSA (TruncatedSVD)...")
N_TOPICS = 15
svd = TruncatedSVD(n_components=N_TOPICS, random_state=42)
topic_matrix = svd.fit_transform(tfidf_matrix)
df['main_topic'] = topic_matrix.argmax(axis=1)

print(f"\nExport des figures...")

# 01 — Distribution des clusters DBSCAN
cluster_counts = df[df['cluster'] != -1]['cluster'].value_counts().sort_index()
fig, ax = plt.subplots(figsize=(10, 4))
cluster_counts.plot(kind='bar', ax=ax, color='steelblue', edgecolor='white')
ax.set_title('Nombre de produits par cluster DBSCAN')
ax.set_xlabel('Cluster')
ax.set_ylabel('Nombre de produits')
plt.tight_layout()
fig.savefig(OUTPUT_DIR / "01_cluster_distribution.png", dpi=150, bbox_inches='tight')
plt.close()
print("  01_cluster_distribution.png")

# 02 — Distribution des topics LSA
topic_counts = df['main_topic'].value_counts().sort_index()
fig, ax = plt.subplots(figsize=(12, 4))
topic_counts.plot(kind='bar', ax=ax, color='seagreen', edgecolor='white')
ax.set_title('Nombre de produits par topic dominant (LSA)')
ax.set_xlabel('Topic')
ax.set_ylabel('Nombre de produits')
plt.tight_layout()
fig.savefig(OUTPUT_DIR / "02_topic_distribution.png", dpi=150, bbox_inches='tight')
plt.close()
print("  02_topic_distribution.png")

# 03 — Wordclouds DBSCAN
clusters_to_show = sorted([c for c in df['cluster'].unique() if c != -1])
n = len(clusters_to_show)
cols = 3
rows = (n + cols - 1) // cols

fig, axes = plt.subplots(rows, cols, figsize=(15, rows * 4))
axes = axes.flatten()

for i, cluster_id in enumerate(clusters_to_show):
    texts = ' '.join(df[df['cluster'] == cluster_id]['description_processed'])
    wc = WordCloud(width=400, height=300, background_color='white',
                   max_words=30, colormap='Blues').generate(texts)
    axes[i].imshow(wc, interpolation='bilinear')
    axes[i].set_title(f'Cluster {cluster_id} ({len(df[df["cluster"]==cluster_id])} produits)', fontsize=10)
    axes[i].axis('off')

for j in range(i + 1, len(axes)):
    axes[j].axis('off')

plt.suptitle('Wordclouds par cluster DBSCAN', fontsize=13)
plt.tight_layout()
fig.savefig(OUTPUT_DIR / "03_dbscan_wordclouds.png", dpi=150, bbox_inches='tight')
plt.close()
print("  03_dbscan_wordclouds.png")

# 04 — Wordclouds LSA
cols = 3
rows = (N_TOPICS + cols - 1) // cols

fig, axes = plt.subplots(rows, cols, figsize=(15, rows * 4))
axes = axes.flatten()

for i in range(N_TOPICS):
    components = svd.components_[i]
    word_weights = {feature_names[j]: max(components[j], 0) for j in range(len(feature_names))}
    word_weights = {k: v for k, v in word_weights.items() if v > 0}

    if word_weights:
        wc = WordCloud(width=400, height=300, background_color='white',
                       max_words=25, colormap='Greens').generate_from_frequencies(word_weights)
        axes[i].imshow(wc, interpolation='bilinear')
    axes[i].set_title(f'Topic {i} ({len(df[df["main_topic"]==i])} produits)', fontsize=10)
    axes[i].axis('off')

for j in range(N_TOPICS, len(axes)):
    axes[j].axis('off')

plt.suptitle('Wordclouds par topic (LSA / TruncatedSVD)', fontsize=13)
plt.tight_layout()
fig.savefig(OUTPUT_DIR / "04_lsa_wordclouds.png", dpi=150, bbox_inches='tight')
plt.close()
print("  04_lsa_wordclouds.png")

print(f"\nDone — 4 figures exportées dans {OUTPUT_DIR}")
