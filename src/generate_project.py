from __future__ import annotations
from pathlib import Path
import json, math, random, pickle
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import roc_auc_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
for d in ['data/raw','data/processed','models','visuals','dashboard','public','reports','notebooks','sql','streamlit_app','powerbi']:
    (ROOT/d).mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(42)
random.seed(42)

countries = ['India','United States','United Kingdom','Brazil','Germany','Japan','South Korea','Canada','Australia','France','Mexico','Spain']
country_weights = np.array([.18,.16,.08,.08,.07,.07,.07,.07,.06,.06,.05,.05]); country_weights /= country_weights.sum()
plans = pd.DataFrame({
    'Plan_ID':['P_BASIC','P_STANDARD','P_PREMIUM','P_MOBILE'],
    'Subscription_Type':['Basic','Standard','Premium','Mobile'],
    'Monthly_Price_USD':[7.99,12.99,18.99,4.99],
    'Max_Streams':[1,2,4,1],
    'Resolution':['HD','Full HD','4K Ultra HD','Mobile HD']
})
plans.to_csv(ROOT/'data/raw/subscription_plans.csv', index=False)

n_users=24000
user_ids=[f'U{100000+i}' for i in range(n_users)]
subs = rng.choice(['Basic','Standard','Premium','Mobile'], n_users, p=[.28,.32,.26,.14])
ages = np.clip(rng.normal(34, 12, n_users).astype(int), 16, 75)
signup_start = np.datetime64('2022-01-01')
signup_dates = signup_start + rng.integers(0, 1460, n_users).astype('timedelta64[D]')
user_country = rng.choice(countries, n_users, p=country_weights)
base_watch = rng.gamma(2.2, 18, n_users)
sub_mult = pd.Series(subs).map({'Mobile':.75,'Basic':.9,'Standard':1.1,'Premium':1.35}).to_numpy()
watch_hours = np.round(base_watch*sub_mult + rng.normal(0,5,n_users),2).clip(0)
churn_prob = 1/(1+np.exp(-(-1.1 + (25-watch_hours)/20 + (subs=='Mobile')*.45 + (subs=='Premium')*(-.45) + (ages<22)*.25)))
churn = rng.binomial(1, churn_prob)
users = pd.DataFrame({
    'User_ID':user_ids,'Age':ages,'Country':user_country,'Subscription_Type':subs,
    'Signup_Date':pd.to_datetime(signup_dates).strftime('%Y-%m-%d'),'Watch_Hours':watch_hours,'Churn_Status':np.where(churn==1,'Churned','Active')
})
users.to_csv(ROOT/'data/raw/users.csv', index=False)

# Content library
n_content=1500
genres=['Drama','Comedy','Action','Thriller','Romance','Documentary','Sci-Fi','Fantasy','Crime','Kids','Anime','Reality','Horror','Sports']
languages=['English','Hindi','Spanish','Korean','Japanese','French','German','Portuguese','Tamil','Telugu']
content_type=rng.choice(['Movie','TV Show'], n_content, p=[.58,.42])
genre_weights=np.array([.15,.12,.11,.10,.08,.07,.08,.07,.08,.06,.06,.04,.05,.03]); genre_weights=genre_weights/genre_weights.sum()
genre=rng.choice(genres, n_content, p=genre_weights)
release_year=rng.integers(1995,2027,n_content)
duration=np.where(content_type=='Movie', rng.integers(80,180,n_content), rng.integers(24,62,n_content))
imdb=np.round(np.clip(rng.normal(7.1, .9, n_content) + np.isin(genre,['Drama','Documentary','Crime'])*.25, 3.5, 9.8),1)
lang=rng.choice(languages, n_content, p=[.42,.15,.1,.08,.07,.05,.04,.04,.025,.025])
content=pd.DataFrame({
    'Content_ID':[f'C{200000+i}' for i in range(n_content)],
    'Title':[f'{g} {t} #{i:04d}' for i,(g,t) in enumerate(zip(genre,content_type))],
    'Content_Type':content_type,'Genre':genre,'Release_Year':release_year,'IMDB_Rating':imdb,'Duration':duration,'Language':lang,
    'Original_Flag':rng.choice(['Netflix Original','Licensed'], n_content, p=[.38,.62]),
    'Release_Date':(pd.to_datetime('2022-01-01') + pd.to_timedelta(rng.integers(0,1460,n_content), unit='D')).strftime('%Y-%m-%d')
})
content.to_csv(ROOT/'data/raw/content_library.csv', index=False)

# Devices per user
n_devices=36000
dev_types=['Smart TV','Mobile','Tablet','Desktop','Game Console']
devices=pd.DataFrame({
    'Device_ID':[f'D{300000+i}' for i in range(n_devices)],
    'User_ID':rng.choice(user_ids,n_devices),
    'Device_Type':rng.choice(dev_types,n_devices,p=[.31,.36,.11,.17,.05]),
    'OS':rng.choice(['Android','iOS','WebOS','Tizen','Windows','macOS','PlayStation','Xbox'],n_devices),
    'Last_Active_Date':(pd.to_datetime('2025-12-31')-pd.to_timedelta(rng.integers(0,240,n_devices),unit='D')).strftime('%Y-%m-%d')
}).drop_duplicates(['User_ID','Device_Type']).reset_index(drop=True)
devices.to_csv(ROOT/'data/raw/devices.csv', index=False)

# Watch history 130k sessions
n_sessions=132000
session_user=rng.choice(user_ids,n_sessions, p=(watch_hours+2)/(watch_hours+2).sum())
content_pop=(content['IMDB_Rating'].to_numpy()-3) * np.where(content['Original_Flag'].eq('Netflix Original'),1.25,1) * (1+(2026-content['Release_Year'].to_numpy())/80)
content_pop=content_pop/content_pop.sum()
session_content=rng.choice(content['Content_ID'].to_numpy(), n_sessions, p=content_pop)
base_dates=pd.to_datetime('2024-01-01')+pd.to_timedelta(rng.integers(0,730,n_sessions),unit='D')
hour_weights=np.array([.025,.015,.01,.006,.004,.004,.008,.018,.026,.03,.032,.035,.04,.043,.047,.052,.06,.07,.085,.095,.09,.075,.05,.035]); hour_weights=hour_weights/hour_weights.sum()
hours=rng.choice(range(24), n_sessions, p=hour_weights)
watch_time=base_dates+pd.to_timedelta(hours,unit='h')+pd.to_timedelta(rng.integers(0,60,n_sessions),unit='m')
content_map=content.set_index('Content_ID')
cont_duration=content_map.loc[session_content,'Duration'].to_numpy()
cont_genre=content_map.loc[session_content,'Genre'].to_numpy()
dev = rng.choice(dev_types,n_sessions,p=[.30,.39,.10,.16,.05])
completion_base = rng.beta(4.3,2.1,n_sessions)
completion_base += np.isin(cont_genre,['Kids','Comedy','Anime'])*.06 - np.isin(cont_genre,['Documentary','Horror'])*.04 + (dev=='Mobile')*.03
completion=np.clip(completion_base, .02, 1.0)
watch_duration=np.round(cont_duration*completion,1)
watch_history=pd.DataFrame({
    'Session_ID':[f'S{500000+i}' for i in range(n_sessions)], 'User_ID':session_user, 'Content_ID':session_content,
    'Watch_Time':watch_time.strftime('%Y-%m-%d %H:%M:%S'), 'Completion_Rate':np.round(completion,3),
    'Device_Type':dev, 'Watch_Duration':watch_duration
})
watch_history.to_csv(ROOT/'data/raw/watch_history.csv', index=False)

# Reviews
review_idx=rng.choice(np.arange(n_sessions), 52000, replace=False)
review_sessions=watch_history.iloc[review_idx]
sent_words_pos=['gripping','brilliant','addictive','cinematic','emotional','rewatchable','premium','fresh']
sent_words_neg=['slow','predictable','flat','confusing','forgettable','overhyped','weak','dragging']
ratings=[]; texts=[]
for cr in review_sessions['Completion_Rate'].to_numpy():
    rating=int(np.clip(round(1 + cr*4 + rng.normal(0,.75)),1,5))
    ratings.append(rating)
    pool=sent_words_pos if rating>=4 else sent_words_neg if rating<=2 else sent_words_pos[:4]+sent_words_neg[:4]
    texts.append(' '.join(rng.choice(pool, size=5, replace=True)))
reviews=pd.DataFrame({'Review_ID':[f'R{700000+i}' for i in range(len(review_sessions))], 'Session_ID':review_sessions['Session_ID'].to_numpy(), 'User_ID':review_sessions['User_ID'].to_numpy(), 'Content_ID':review_sessions['Content_ID'].to_numpy(), 'Rating':ratings, 'Review_Text':texts, 'Review_Date':pd.to_datetime(review_sessions['Watch_Time']).dt.strftime('%Y-%m-%d')})
reviews.to_csv(ROOT/'data/raw/reviews.csv', index=False)

# Enriched marts
wh=watch_history.copy(); wh['Watch_Time']=pd.to_datetime(wh['Watch_Time']); wh['Watch_Date']=wh['Watch_Time'].dt.date; wh['Month']=wh['Watch_Time'].dt.to_period('M').astype(str); wh['Weekday']=wh['Watch_Time'].dt.day_name(); wh['Is_Weekend']=wh['Watch_Time'].dt.dayofweek>=5
enriched=wh.merge(users,on='User_ID').merge(content,on='Content_ID').merge(plans,on='Subscription_Type')
enriched['Revenue_USD']=enriched['Monthly_Price_USD']/30
enriched.to_csv(ROOT/'data/processed/watch_enriched.csv', index=False)
monthly=enriched.groupby('Month',as_index=False).agg(Watch_Hours=('Watch_Duration',lambda s:s.sum()/60), Sessions=('Session_ID','count'), Active_Users=('User_ID','nunique'), Revenue_USD=('Revenue_USD','sum'), Avg_Completion=('Completion_Rate','mean'))
monthly['Watch_Growth_Rate']=monthly['Watch_Hours'].pct_change().fillna(0)
monthly.to_csv(ROOT/'data/processed/monthly_kpis.csv', index=False)
genre_perf=enriched.groupby('Genre',as_index=False).agg(Watch_Hours=('Watch_Duration',lambda s:s.sum()/60), Sessions=('Session_ID','count'), Active_Users=('User_ID','nunique'), Avg_Completion=('Completion_Rate','mean'), Revenue_USD=('Revenue_USD','sum'), Avg_IMDB=('IMDB_Rating','mean'))
genre_perf['Engagement_Score']=genre_perf['Watch_Hours']*.45+genre_perf['Avg_Completion']*10000*.35+genre_perf['Active_Users']*.20
genre_perf.sort_values('Engagement_Score', ascending=False).to_csv(ROOT/'data/processed/genre_performance.csv', index=False)
user_features=enriched.groupby('User_ID',as_index=False).agg(total_watch_minutes=('Watch_Duration','sum'), sessions=('Session_ID','count'), avg_completion=('Completion_Rate','mean'), unique_genres=('Genre','nunique'), weekend_share=('Is_Weekend','mean'), mobile_share=('Device_Type',lambda s:(s=='Mobile').mean()), revenue=('Revenue_USD','sum'))
user_features=user_features.merge(users[['User_ID','Age','Country','Subscription_Type','Churn_Status']],on='User_ID')
Xseg=user_features[['total_watch_minutes','sessions','avg_completion','unique_genres','weekend_share','mobile_share','revenue']]
seg_scaled=StandardScaler().fit_transform(Xseg)
kmeans=KMeans(n_clusters=5, random_state=42, n_init=10).fit(seg_scaled)
user_features['Viewer_Segment_ID']=kmeans.labels_
segment_names={0:'Casual Browsers',1:'Global Bingers',2:'Premium Loyalists',3:'At-Risk Low Engagement',4:'Genre Explorers'}
# assign labels by engagement rank for cleaner storytelling
rank=user_features.groupby('Viewer_Segment_ID')['total_watch_minutes'].mean().sort_values().index.tolist()
name_order=['At-Risk Low Engagement','Casual Browsers','Genre Explorers','Premium Loyalists','Global Bingers']
label_map={cid:name_order[i] for i,cid in enumerate(rank)}
user_features['Viewer_Segment']=user_features['Viewer_Segment_ID'].map(label_map)
user_features.to_csv(ROOT/'data/processed/viewer_segments.csv', index=False)
with open(ROOT/'models/viewer_segmentation_kmeans.pkl','wb') as f: pickle.dump(kmeans,f)

# churn model
model_df=pd.get_dummies(user_features.drop(columns=['User_ID','Country','Viewer_Segment','Viewer_Segment_ID']), columns=['Subscription_Type'], drop_first=True)
y=(model_df.pop('Churn_Status')=='Churned').astype(int)
X_train,X_test,y_train,y_test=train_test_split(model_df,y,test_size=.25,random_state=42,stratify=y)
clf=RandomForestClassifier(n_estimators=160,max_depth=10,min_samples_leaf=12,random_state=42,n_jobs=-1).fit(X_train,y_train)
pred=clf.predict_proba(X_test)[:,1]
with open(ROOT/'models/churn_prediction_random_forest.pkl','wb') as f: pickle.dump({'model':clf,'features':model_df.columns.tolist()},f)

# simple recommendation seed based on segment + genre popularity
recs=[]
for seg in user_features['Viewer_Segment'].unique():
    seg_users=user_features.loc[user_features['Viewer_Segment'].eq(seg),'User_ID']
    top_genres=enriched[enriched['User_ID'].isin(seg_users)].groupby('Genre')['Watch_Duration'].sum().sort_values(ascending=False).head(3).index.tolist()
    cand=content[content['Genre'].isin(top_genres)].sort_values(['IMDB_Rating','Release_Year'],ascending=False).head(10)
    for _,r in cand.iterrows(): recs.append({'Viewer_Segment':seg,'Recommended_Content_ID':r.Content_ID,'Title':r.Title,'Genre':r.Genre,'IMDB_Rating':r.IMDB_Rating})
pd.DataFrame(recs).to_csv(ROOT/'models/recommendation_preview.csv', index=False)

# sentiment model/simple scoring
sentiment=reviews.copy()
sentiment['Sentiment_Label']=np.where(sentiment['Rating']>=4,'Positive',np.where(sentiment['Rating']<=2,'Negative','Neutral'))
sentiment.to_csv(ROOT/'data/processed/review_sentiment.csv', index=False)

# forecasting inputs
forecast=monthly[['Month','Watch_Hours']].copy(); forecast['t']=np.arange(len(forecast)); lr=LinearRegression().fit(forecast[['t']], forecast['Watch_Hours'])
future_t=np.arange(len(forecast), len(forecast)+6)
future_month=pd.period_range(pd.Period(forecast['Month'].iloc[-1],freq='M')+1, periods=6, freq='M').astype(str)
future=pd.DataFrame({'Month':future_month,'Forecast_Watch_Hours':lr.predict(future_t.reshape(-1,1))})
future.to_csv(ROOT/'data/processed/watch_time_forecast.csv', index=False)

metrics={'roc_auc':float(roc_auc_score(y_test,pred)), 'churn_rate':float(y.mean()), 'sessions':int(n_sessions), 'users':int(n_users), 'content_titles':int(n_content), 'reviews':int(len(reviews)), 'model_features':model_df.columns.tolist()}
(ROOT/'models/model_metrics.json').write_text(json.dumps(metrics,indent=2))

# Lightweight SVG visuals
visual = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675" viewBox="0 0 1200 675"><defs><linearGradient id="g" x1="0" x2="1"><stop stop-color="#e50914"/><stop offset="1" stop-color="#00f5ff"/></linearGradient></defs><rect width="1200" height="675" fill="#05010d"/><g opacity=".25" stroke="#e50914">{''.join(f'<line x1="{x}" y1="0" x2="{x-220}" y2="675"/>' for x in range(0,1500,70))}</g><text x="70" y="130" fill="#fff" font-size="54" font-family="Arial" font-weight="800">Netflix Content Strategy Analytics</text><text x="70" y="190" fill="#a7b1d8" font-size="26" font-family="Arial">Cyberpunk executive dashboard • engagement • churn • revenue • recommendations</text><rect x="70" y="260" width="250" height="140" rx="24" fill="#121735" stroke="#e50914"/><text x="95" y="315" fill="#a7b1d8" font-size="20" font-family="Arial">Watch Sessions</text><text x="95" y="370" fill="#00f5ff" font-size="44" font-family="Arial" font-weight="800">{n_sessions:,}</text><rect x="350" y="260" width="250" height="140" rx="24" fill="#121735" stroke="#00f5ff"/><text x="375" y="315" fill="#a7b1d8" font-size="20" font-family="Arial">Users</text><text x="375" y="370" fill="#e50914" font-size="44" font-family="Arial" font-weight="800">{n_users:,}</text><rect x="630" y="260" width="250" height="140" rx="24" fill="#121735" stroke="#e50914"/><text x="655" y="315" fill="#a7b1d8" font-size="20" font-family="Arial">Churn AUC</text><text x="655" y="370" fill="#9dff00" font-size="44" font-family="Arial" font-weight="800">{metrics['roc_auc']:.2f}</text><rect x="910" y="260" width="220" height="140" rx="24" fill="#121735" stroke="#00f5ff"/><text x="935" y="315" fill="#a7b1d8" font-size="20" font-family="Arial">Titles</text><text x="935" y="370" fill="#fff" font-size="44" font-family="Arial" font-weight="800">{n_content:,}</text><path d="M90 550 C260 460 370 565 520 480 S805 535 1030 430" fill="none" stroke="url(#g)" stroke-width="10" stroke-linecap="round"/></svg>'''
(ROOT/'visuals/dashboard_overview.svg').write_text(visual)
print('Generated OTT analytics project data and models:', metrics)
