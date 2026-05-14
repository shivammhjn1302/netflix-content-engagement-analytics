-- Netflix Content Strategy & Viewer Engagement Analytics: 35 advanced SQL queries
-- Dialect: PostgreSQL/Snowflake-style analytical SQL. Adapt DATE_TRUNC/DATE_DIFF syntax as needed.

-- 01. Executive streaming KPI summary
WITH sessions AS (
  SELECT wh.*, u.subscription_type, u.churn_status, sp.monthly_price_usd
  FROM watch_history wh JOIN users u ON wh.user_id=u.user_id JOIN subscription_plans sp ON u.subscription_type=sp.subscription_type
)
SELECT COUNT(*) watch_sessions, COUNT(DISTINCT user_id) active_users, SUM(watch_duration)/60.0 watch_hours, AVG(completion_rate) avg_completion, SUM(monthly_price_usd/30.0) revenue_proxy FROM sessions;

-- 02. Daily active users and watch hours
SELECT CAST(watch_time AS DATE) watch_date, COUNT(DISTINCT user_id) dau, COUNT(*) sessions, SUM(watch_duration)/60.0 watch_hours FROM watch_history GROUP BY 1 ORDER BY 1;

-- 03. Monthly watch-time growth
WITH m AS (SELECT DATE_TRUNC('month', watch_time) month, SUM(watch_duration)/60.0 watch_hours FROM watch_history GROUP BY 1)
SELECT month, watch_hours, LAG(watch_hours) OVER(ORDER BY month) prior_month, (watch_hours-LAG(watch_hours) OVER(ORDER BY month))/NULLIF(LAG(watch_hours) OVER(ORDER BY month),0) growth_rate FROM m ORDER BY month;

-- 04. Most watched genres
SELECT c.genre, COUNT(*) sessions, SUM(w.watch_duration)/60.0 watch_hours, AVG(w.completion_rate) avg_completion FROM watch_history w JOIN content_library c ON w.content_id=c.content_id GROUP BY 1 ORDER BY watch_hours DESC;

-- 05. Top performing shows and movies
SELECT c.title, c.content_type, c.genre, COUNT(*) sessions, SUM(w.watch_duration) minutes_watched, AVG(w.completion_rate) avg_completion, RANK() OVER(ORDER BY SUM(w.watch_duration) DESC) content_rank FROM watch_history w JOIN content_library c ON w.content_id=c.content_id GROUP BY 1,2,3 ORDER BY content_rank LIMIT 50;

-- 06. Content engagement score
WITH perf AS (SELECT c.content_id,c.title,c.genre,COUNT(*) sessions,COUNT(DISTINCT w.user_id) viewers,SUM(w.watch_duration)/60.0 watch_hours,AVG(w.completion_rate) completion FROM watch_history w JOIN content_library c ON w.content_id=c.content_id GROUP BY 1,2,3)
SELECT *, (watch_hours*.45 + viewers*.25 + completion*1000*.30) engagement_score FROM perf ORDER BY engagement_score DESC;

-- 07. Churn rate by subscription type
SELECT subscription_type, AVG(CASE WHEN churn_status='Churned' THEN 1 ELSE 0 END) churn_rate, COUNT(*) users FROM users GROUP BY subscription_type ORDER BY churn_rate DESC;

-- 08. Retention cohort by signup month
WITH cohorts AS (SELECT user_id, DATE_TRUNC('month', signup_date) cohort_month FROM users), activity AS (SELECT DISTINCT user_id, DATE_TRUNC('month', watch_time) activity_month FROM watch_history), indexed AS (SELECT c.cohort_month, a.activity_month, DATE_DIFF('month', c.cohort_month, a.activity_month) cohort_index, a.user_id FROM cohorts c JOIN activity a ON c.user_id=a.user_id)
SELECT cohort_month, cohort_index, COUNT(DISTINCT user_id) retained_users FROM indexed GROUP BY 1,2 ORDER BY 1,2;

-- 09. Binge watching behavior by device
WITH daily AS (SELECT user_id, device_type, CAST(watch_time AS DATE) watch_date, COUNT(*) sessions, SUM(watch_duration) minutes FROM watch_history GROUP BY 1,2,3)
SELECT device_type, AVG(CASE WHEN sessions>=3 OR minutes>=180 THEN 1 ELSE 0 END) binge_day_rate, AVG(minutes) avg_daily_minutes FROM daily GROUP BY device_type ORDER BY binge_day_rate DESC;

-- 10. Weekend watch-time spike
SELECT CASE WHEN EXTRACT(dow FROM watch_time) IN (0,6) THEN 'Weekend' ELSE 'Weekday' END day_type, COUNT(*) sessions, SUM(watch_duration)/60.0 watch_hours, AVG(completion_rate) completion FROM watch_history GROUP BY 1;

-- 11. Country-wise engagement
SELECT u.country, COUNT(DISTINCT w.user_id) viewers, COUNT(*) sessions, SUM(w.watch_duration)/60.0 watch_hours, AVG(w.completion_rate) avg_completion FROM watch_history w JOIN users u ON w.user_id=u.user_id GROUP BY 1 ORDER BY watch_hours DESC;

-- 12. Premium plan adoption trend
SELECT DATE_TRUNC('month', signup_date) signup_month, AVG(CASE WHEN subscription_type='Premium' THEN 1 ELSE 0 END) premium_adoption FROM users GROUP BY 1 ORDER BY 1;

-- 13. Revenue per user by country
SELECT u.country, SUM(sp.monthly_price_usd) monthly_arr, COUNT(*) users, SUM(sp.monthly_price_usd)/COUNT(*) revenue_per_user FROM users u JOIN subscription_plans sp ON u.subscription_type=sp.subscription_type GROUP BY 1 ORDER BY revenue_per_user DESC;

-- 14. Device usage share
SELECT device_type, COUNT(*) sessions, COUNT(*)*1.0/SUM(COUNT(*)) OVER() session_share, AVG(completion_rate) avg_completion FROM watch_history GROUP BY device_type ORDER BY sessions DESC;

-- 15. Genre preference by country
WITH x AS (SELECT u.country,c.genre,SUM(w.watch_duration) minutes FROM watch_history w JOIN users u ON w.user_id=u.user_id JOIN content_library c ON w.content_id=c.content_id GROUP BY 1,2)
SELECT * FROM (SELECT x.*, ROW_NUMBER() OVER(PARTITION BY country ORDER BY minutes DESC) rn FROM x) y WHERE rn<=3 ORDER BY country,rn;

-- 16. Low completion content risk
SELECT c.title,c.genre,c.content_type,COUNT(*) sessions,AVG(w.completion_rate) avg_completion FROM watch_history w JOIN content_library c ON w.content_id=c.content_id GROUP BY 1,2,3 HAVING COUNT(*)>=100 AND AVG(w.completion_rate)<0.55 ORDER BY avg_completion;

-- 17. Review sentiment by genre
SELECT c.genre, AVG(r.rating) avg_rating, AVG(CASE WHEN r.rating>=4 THEN 1 ELSE 0 END) positive_share, COUNT(*) reviews FROM reviews r JOIN content_library c ON r.content_id=c.content_id GROUP BY 1 ORDER BY positive_share DESC;

-- 18. Subscription upgrade candidates
WITH user_engagement AS (SELECT user_id, COUNT(*) sessions, SUM(watch_duration)/60.0 watch_hours, AVG(completion_rate) completion FROM watch_history GROUP BY 1)
SELECT u.user_id,u.country,u.subscription_type,e.watch_hours,e.sessions FROM user_engagement e JOIN users u ON e.user_id=u.user_id WHERE u.subscription_type IN ('Basic','Standard') AND e.watch_hours > (SELECT PERCENTILE_CONT(.8) WITHIN GROUP(ORDER BY watch_hours) FROM user_engagement) ORDER BY e.watch_hours DESC;

-- 19. At-risk active users from engagement drop
WITH m AS (SELECT user_id, DATE_TRUNC('month', watch_time) month, SUM(watch_duration) minutes FROM watch_history GROUP BY 1,2), seq AS (SELECT *, LAG(minutes) OVER(PARTITION BY user_id ORDER BY month) prior_minutes FROM m)
SELECT * FROM seq WHERE prior_minutes IS NOT NULL AND minutes < prior_minutes*.4 ORDER BY prior_minutes-minutes DESC;

-- 20. Original vs licensed engagement
SELECT c.original_flag, COUNT(*) sessions, SUM(w.watch_duration)/60.0 watch_hours, AVG(w.completion_rate) completion, AVG(c.imdb_rating) imdb FROM watch_history w JOIN content_library c ON w.content_id=c.content_id GROUP BY 1;

-- 21. New release ramp curve
SELECT c.title, DATE_DIFF('day', c.release_date, w.watch_time) days_since_release, COUNT(*) sessions FROM watch_history w JOIN content_library c ON w.content_id=c.content_id WHERE DATE_DIFF('day', c.release_date, w.watch_time) BETWEEN 0 AND 60 GROUP BY 1,2 ORDER BY 1,2;

-- 22. Language demand
SELECT c.language, COUNT(*) sessions, SUM(w.watch_duration)/60.0 watch_hours, COUNT(DISTINCT w.user_id) viewers FROM watch_history w JOIN content_library c ON w.content_id=c.content_id GROUP BY 1 ORDER BY watch_hours DESC;

-- 23. Completion by duration bucket
SELECT CASE WHEN c.duration<30 THEN '<30m' WHEN c.duration<60 THEN '30-59m' WHEN c.duration<100 THEN '60-99m' ELSE '100m+' END duration_bucket, AVG(w.completion_rate) avg_completion, COUNT(*) sessions FROM watch_history w JOIN content_library c ON w.content_id=c.content_id GROUP BY 1 ORDER BY 1;

-- 24. Hour-of-day viewing pattern
SELECT EXTRACT(hour FROM watch_time) hour_of_day, COUNT(*) sessions, SUM(watch_duration)/60.0 watch_hours FROM watch_history GROUP BY 1 ORDER BY 1;

-- 25. Viewer frequency segmentation in SQL
WITH f AS (SELECT user_id, COUNT(*) sessions, SUM(watch_duration)/60.0 hours, AVG(completion_rate) completion FROM watch_history GROUP BY 1)
SELECT *, NTILE(5) OVER(ORDER BY sessions) frequency_quintile, NTILE(5) OVER(ORDER BY hours) watch_time_quintile FROM f;

-- 26. Content retention rate proxy
WITH first_watch AS (SELECT user_id, content_id, MIN(watch_time) first_watch FROM watch_history GROUP BY 1,2), repeat_watch AS (SELECT f.content_id, f.user_id, COUNT(w.session_id) later_sessions FROM first_watch f LEFT JOIN watch_history w ON f.user_id=w.user_id AND f.content_id=w.content_id AND w.watch_time>f.first_watch GROUP BY 1,2)
SELECT c.title,c.genre,AVG(CASE WHEN later_sessions>0 THEN 1 ELSE 0 END) content_retention_rate FROM repeat_watch r JOIN content_library c ON r.content_id=c.content_id GROUP BY 1,2 ORDER BY content_retention_rate DESC;

-- 27. Churned users last watched genres
WITH last_session AS (SELECT w.*, ROW_NUMBER() OVER(PARTITION BY w.user_id ORDER BY w.watch_time DESC) rn FROM watch_history w JOIN users u ON w.user_id=u.user_id WHERE u.churn_status='Churned')
SELECT c.genre, COUNT(*) churned_last_sessions FROM last_session l JOIN content_library c ON l.content_id=c.content_id WHERE rn=1 GROUP BY 1 ORDER BY churned_last_sessions DESC;

-- 28. Rolling 7-day active users
WITH d AS (SELECT CAST(watch_time AS DATE) day, COUNT(DISTINCT user_id) dau FROM watch_history GROUP BY 1)
SELECT day,dau,AVG(dau) OVER(ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) rolling_7d_dau FROM d ORDER BY day;

-- 29. Plan migration opportunity by country
SELECT country, subscription_type, COUNT(*) users, AVG(watch_hours) avg_profile_watch_hours FROM users GROUP BY 1,2 ORDER BY country, avg_profile_watch_hours DESC;

-- 30. Content saturation by genre and release year
SELECT genre, release_year, COUNT(*) titles, AVG(imdb_rating) avg_imdb FROM content_library GROUP BY 1,2 ORDER BY genre, release_year;

-- 31. High IMDB but low discovery titles
WITH perf AS (SELECT c.content_id,c.title,c.genre,c.imdb_rating,COUNT(w.session_id) sessions FROM content_library c LEFT JOIN watch_history w ON c.content_id=w.content_id GROUP BY 1,2,3,4)
SELECT * FROM perf WHERE imdb_rating>=8.0 AND sessions < (SELECT PERCENTILE_CONT(.25) WITHIN GROUP(ORDER BY sessions) FROM perf) ORDER BY imdb_rating DESC;

-- 32. Genre popularity forecasting input
SELECT DATE_TRUNC('month', w.watch_time) month, c.genre, SUM(w.watch_duration)/60.0 watch_hours FROM watch_history w JOIN content_library c ON w.content_id=c.content_id GROUP BY 1,2 ORDER BY 1,2;

-- 33. User home-market content affinity
SELECT u.country,c.language,COUNT(*) sessions,SUM(w.watch_duration)/60.0 watch_hours FROM watch_history w JOIN users u ON w.user_id=u.user_id JOIN content_library c ON w.content_id=c.content_id GROUP BY 1,2 ORDER BY country, watch_hours DESC;

-- 34. Recommendation co-watch pairs
SELECT a.content_id content_a, b.content_id content_b, COUNT(*) shared_viewers FROM watch_history a JOIN watch_history b ON a.user_id=b.user_id AND a.content_id<b.content_id GROUP BY 1,2 HAVING COUNT(*)>=20 ORDER BY shared_viewers DESC;

-- 35. Churn model feature extract
SELECT u.user_id,u.age,u.country,u.subscription_type,u.churn_status,COUNT(w.session_id) sessions,SUM(w.watch_duration) total_watch_minutes,AVG(w.completion_rate) avg_completion,COUNT(DISTINCT c.genre) unique_genres,AVG(CASE WHEN w.device_type='Mobile' THEN 1 ELSE 0 END) mobile_share FROM users u LEFT JOIN watch_history w ON u.user_id=w.user_id LEFT JOIN content_library c ON w.content_id=c.content_id GROUP BY 1,2,3,4,5;
