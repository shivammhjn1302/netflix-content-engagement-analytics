from pathlib import Path
import json
import pickle
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
st.set_page_config(page_title='Netflix Content Strategy Analytics', page_icon='🎬', layout='wide')
st.markdown('''<style>
.stApp{background:radial-gradient(circle at 15% 5%,#3b0710 0,transparent 28%),linear-gradient(135deg,#05010d,#090414 55%,#020a16);color:#f8fbff}.block-container{padding-top:2rem}.metric-card{background:#11162fee;border:1px solid #31385f;border-radius:18px;padding:18px;box-shadow:0 0 24px rgba(229,9,20,.14)}h1,h2,h3{color:#fff}.stMetric label{color:#a8b1d6!important}.stMetric div[data-testid="stMetricValue"]{color:#00f5ff}.stTabs [data-baseweb="tab-list"]{gap:10px}.stTabs [data-baseweb="tab"]{background:#11162f;border-radius:999px;color:#fff;border:1px solid #31385f}
</style>''', unsafe_allow_html=True)

@st.cache_data
def load():
    return {
        'enriched': pd.read_csv(ROOT/'data/processed/watch_enriched.csv', parse_dates=['Watch_Time']),
        'monthly': pd.read_csv(ROOT/'data/processed/monthly_kpis.csv'),
        'genre': pd.read_csv(ROOT/'data/processed/genre_performance.csv'),
        'segments': pd.read_csv(ROOT/'data/processed/viewer_segments.csv'),
        'content': pd.read_csv(ROOT/'data/raw/content_library.csv'),
        'users': pd.read_csv(ROOT/'data/raw/users.csv'),
        'reviews': pd.read_csv(ROOT/'data/processed/review_sentiment.csv'),
        'recs': pd.read_csv(ROOT/'models/recommendation_preview.csv'),
        'metrics': json.loads((ROOT/'models/model_metrics.json').read_text())
    }

data=load(); enriched=data['enriched']
st.title('🎬 Netflix Content Strategy & Viewer Engagement Analytics')
st.caption('Cyberpunk OTT BI dashboard for executive, product, content, and retention strategy teams.')

with st.sidebar:
    st.header('Dynamic Filters')
    countries=st.multiselect('Country', sorted(enriched['Country'].unique()), default=sorted(enriched['Country'].unique())[:6])
    genres=st.multiselect('Genre', sorted(enriched['Genre'].unique()), default=sorted(enriched['Genre'].unique())[:8])
    plans=st.multiselect('Subscription Type', sorted(enriched['Subscription_Type'].unique()), default=sorted(enriched['Subscription_Type'].unique()))

f=enriched[enriched['Country'].isin(countries)&enriched['Genre'].isin(genres)&enriched['Subscription_Type'].isin(plans)]
cols=st.columns(5)
cols[0].metric('Watch Sessions', f'{len(f):,}')
cols[1].metric('Watch Hours', f'{f.Watch_Duration.sum()/60:,.0f}')
cols[2].metric('Avg Completion', f'{f.Completion_Rate.mean()*100:.1f}%')
cols[3].metric('Revenue Proxy', f'${f.Revenue_USD.sum()/1_000_000:.2f}M')
cols[4].metric('Churn AUC', f"{data['metrics']['roc_auc']:.2f}")

tabs=st.tabs(['Executive Overview','Viewer Analytics','Content Performance','Revenue Analytics','Churn Analysis','Recommendations'])
with tabs[0]:
    c1,c2=st.columns([2,1])
    c1.plotly_chart(px.line(data['monthly'], x='Month', y='Watch_Hours', markers=True, title='Monthly Watch-Time Trend', template='plotly_dark'), use_container_width=True)
    c2.plotly_chart(px.pie(f, names='Subscription_Type', values='Revenue_USD', title='Revenue Mix by Plan', hole=.45, template='plotly_dark'), use_container_width=True)
    st.dataframe(data['genre'].head(12), use_container_width=True)
with tabs[1]:
    seg=data['segments'].groupby('Viewer_Segment', as_index=False).agg(Users=('User_ID','count'), Watch_Minutes=('total_watch_minutes','sum'), Avg_Completion=('avg_completion','mean'), Revenue=('revenue','sum'))
    st.plotly_chart(px.bar(seg, x='Viewer_Segment', y='Watch_Minutes', color='Viewer_Segment', title='Viewer Segments by Engagement', template='plotly_dark'), use_container_width=True)
    st.plotly_chart(px.scatter(data['segments'], x='sessions', y='total_watch_minutes', color='Viewer_Segment', size='revenue', hover_data=['Subscription_Type'], title='Viewer Engagement Clusters', template='plotly_dark'), use_container_width=True)
with tabs[2]:
    content_perf=f.groupby(['Title','Genre','Content_Type'], as_index=False).agg(Sessions=('Session_ID','count'), Watch_Minutes=('Watch_Duration','sum'), Avg_Completion=('Completion_Rate','mean')).sort_values('Watch_Minutes', ascending=False)
    st.plotly_chart(px.bar(content_perf.head(20), x='Watch_Minutes', y='Title', color='Genre', orientation='h', title='Top Performing Titles', template='plotly_dark'), use_container_width=True)
    st.plotly_chart(px.treemap(f, path=['Genre','Content_Type'], values='Watch_Duration', color='Completion_Rate', title='Genre Engagement Tree Map'), use_container_width=True)
with tabs[3]:
    rev=f.groupby(['Subscription_Type','Country'], as_index=False).agg(Revenue=('Revenue_USD','sum'), Users=('User_ID','nunique'))
    st.plotly_chart(px.bar(rev, x='Country', y='Revenue', color='Subscription_Type', title='Revenue by Country and Plan', template='plotly_dark'), use_container_width=True)
with tabs[4]:
    users=data['users']; churn=users.groupby(['Subscription_Type','Churn_Status'], as_index=False).size()
    st.plotly_chart(px.bar(churn, x='Subscription_Type', y='size', color='Churn_Status', barmode='group', title='Churn by Subscription Plan', template='plotly_dark'), use_container_width=True)
    st.info('Model uses viewing frequency, watch minutes, completion behavior, weekend/mobile share, revenue proxy, age, and plan type.')
with tabs[5]:
    segment=st.selectbox('Select viewer segment', sorted(data['recs']['Viewer_Segment'].unique()))
    st.dataframe(data['recs'][data['recs']['Viewer_Segment'].eq(segment)], use_container_width=True)
    st.download_button('Download filtered sessions CSV', f.to_csv(index=False), file_name='filtered_watch_sessions.csv')
