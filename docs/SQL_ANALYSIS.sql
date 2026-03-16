SELECT 
    DATE(observed_at) AS day,
    AVG((data->>'rssi')::float) AS avg_rssi,
    MAX((data->>'rssi')::float) AS max_rssi,
    MIN((data->>'rssi')::float) AS min_rssi,
    STDDEV((data->>'rssi')::float) AS stddev_rssi
FROM aircraft_positions_history
WHERE observed_at >= NOW() - INTERVAL '10 days'
GROUP BY DATE(observed_at)
ORDER BY day;