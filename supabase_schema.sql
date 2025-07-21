-- Supabase Database Schema for Non-Commercial Dashboard
-- Key Liquidity (KL) Zones Storage

-- Drop the existing kl_zones table if it exists
DROP TABLE IF EXISTS kl_zones CASCADE;

-- Create the kl_zones table with all required fields for KL entry
CREATE TABLE kl_zones (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    cot_asset_name VARCHAR(100), -- No longer NOT NULL
    kl_type VARCHAR(20) NOT NULL CHECK (kl_type IN ('Swing High', 'Swing Low', 'General')),
    zone_high DECIMAL(15, 5) NOT NULL,
    zone_low DECIMAL(15, 5) NOT NULL,
    zone_size DECIMAL(15, 5) NOT NULL,
    atr_value DECIMAL(15, 5) NOT NULL,
    atr_multiplier DECIMAL(5, 2) DEFAULT 2.0,
    cot_net_change DECIMAL(10, 6),
    candle_label TEXT NOT NULL,
    time_period VARCHAR(10) NOT NULL CHECK (time_period IN ('weekly', 'quarterly')),
    chart_interval VARCHAR(10) NOT NULL DEFAULT '1h',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    session_id VARCHAR(100),
    user_notes TEXT,
    CONSTRAINT valid_zone CHECK (zone_high > zone_low),
    CONSTRAINT valid_atr CHECK (atr_value > 0),
    CONSTRAINT valid_zone_size CHECK (zone_size > 0),
    CONSTRAINT unique_symbol_candlelabel UNIQUE (symbol, candle_label)
);

-- Indexes for performance
CREATE INDEX idx_kl_zones_symbol ON kl_zones(symbol);
CREATE INDEX idx_kl_zones_datetime ON kl_zones(created_at);
CREATE INDEX idx_kl_zones_type ON kl_zones(kl_type);
CREATE INDEX idx_kl_zones_period ON kl_zones(time_period);
CREATE INDEX idx_kl_zones_session ON kl_zones(session_id);

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_kl_zones_updated_at 
    BEFORE UPDATE ON kl_zones 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Create a view for KL zones with calculated fields
CREATE OR REPLACE VIEW kl_zones_summary AS
SELECT 
    id,
    symbol,
    cot_asset_name,
    kl_type,
    zone_high,
    zone_low,
    zone_size,
    (zone_high + zone_low) / 2 as zone_midpoint,
    zone_high - zone_low as zone_range,
    atr_value,
    atr_multiplier,
    cot_net_change,
    candle_label,
    time_period,
    chart_interval,
    created_at,
    user_notes
FROM kl_zones
ORDER BY created_at DESC;

-- Create a function to get KL zones for a specific symbol and time period
CREATE OR REPLACE FUNCTION get_kl_zones_for_symbol(
    p_symbol VARCHAR(20),
    p_time_period VARCHAR(10) DEFAULT 'weekly'
)
RETURNS TABLE (
    id UUID,
    symbol VARCHAR(20),
    kl_type VARCHAR(20),
    zone_high DECIMAL(15, 5),
    zone_low DECIMAL(15, 5),
    zone_midpoint DECIMAL(15, 5),
    zone_size DECIMAL(15, 5),
    cot_net_change DECIMAL(10, 6),
    candle_label TEXT,
    time_period VARCHAR(10),
    chart_interval VARCHAR(10),
    created_at TIMESTAMP WITH TIME ZONE,
    user_notes TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        kz.id,
        kz.symbol,
        kz.kl_type,
        kz.zone_high,
        kz.zone_low,
        (kz.zone_high + kz.zone_low) / 2 as zone_midpoint,
        kz.zone_size,
        kz.cot_net_change,
        kz.candle_label,
        kz.time_period,
        kz.chart_interval,
        kz.created_at,
        kz.user_notes
    FROM kl_zones kz
    WHERE kz.symbol = p_symbol 
    AND kz.time_period = p_time_period
    ORDER BY kz.created_at DESC;
END;
$$ LANGUAGE plpgsql;

-- Create a function to get KL zones summary statistics
CREATE OR REPLACE FUNCTION get_kl_zones_stats(
    p_symbol VARCHAR(20),
    p_time_period VARCHAR(10) DEFAULT 'weekly'
)
RETURNS TABLE (
    total_zones BIGINT,
    avg_zone_size DECIMAL(15, 5),
    avg_cot_change DECIMAL(10, 6),
    swing_high_count BIGINT,
    swing_low_count BIGINT,
    general_count BIGINT,
    latest_kl_datetime TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*) as total_zones,
        AVG(zone_size) as avg_zone_size,
        AVG(cot_net_change) as avg_cot_change,
        COUNT(*) FILTER (WHERE kl_type = 'Swing High') as swing_high_count,
        COUNT(*) FILTER (WHERE kl_type = 'Swing Low') as swing_low_count,
        COUNT(*) FILTER (WHERE kl_type = 'General') as general_count,
        MAX(created_at) as latest_kl_datetime
    FROM kl_zones
    WHERE symbol = p_symbol 
    AND time_period = p_time_period;
END;
$$ LANGUAGE plpgsql;

-- Enable Row Level Security (for future user authentication)
ALTER TABLE kl_zones ENABLE ROW LEVEL SECURITY;

-- Create policy for public read access (adjust based on your security needs)
CREATE POLICY "Allow public read access" ON kl_zones
    FOR SELECT USING (true);

-- Create policy for public insert access (adjust based on your security needs)
CREATE POLICY "Allow public insert access" ON kl_zones
    FOR INSERT WITH CHECK (true);

-- Create policy for public update access (adjust based on your security needs)
CREATE POLICY "Allow public update access" ON kl_zones
    FOR UPDATE USING (true);

-- Create policy for public delete access (adjust based on your security needs)
CREATE POLICY "Allow public delete access" ON kl_zones
    FOR DELETE USING (true);

-- Insert sample data (optional - for testing)
-- INSERT INTO kl_zones (
--     symbol, cot_asset_name, kl_type, zone_high, zone_low, zone_size,
--     atr_value, cot_net_change, clicked_price, clicked_datetime, 
--     clicked_point_index, time_period, session_id
-- ) VALUES (
--     'GC=F', 'GOLD - COMMODITY EXCHANGE INC.', 'Swing High', 
--     2050.50, 2040.50, 10.00, 5.25, 0.0234, 2045.00, 
--     '2024-01-15 14:00:00+00', 100, 'weekly', 'test_session_1'
-- ); 

ALTER TABLE kl_zones
ADD COLUMN IF NOT EXISTS candle_label text;

-- Add unique constraint for (symbol, time_period, candle_label)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'unique_symbol_period_candlelabel'
          AND table_name = 'kl_zones'
    ) THEN
        ALTER TABLE kl_zones
        ADD CONSTRAINT unique_symbol_period_candlelabel UNIQUE (symbol, time_period, candle_label);
    END IF;
END$$; 