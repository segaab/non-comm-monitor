import os
import uuid
from datetime import datetime
from typing import List, Dict, Optional
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv
import streamlit as st
import logging

# Set up logging
logging.basicConfig(filename='supabase_client.log', level=logging.ERROR, format='%(asctime)s %(levelname)s %(message)s')

# Load environment variables
load_dotenv()

class SupabaseKLClient:
    """Client for managing KL zones in Supabase database"""
    
    def __init__(self):
        """Initialize Supabase client"""
        self.supabase_url = "https://dzddytphimhoxeccxqsw.supabase.co"
        self.supabase_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImR6ZGR5dHBoaW1ob3hlY2N4cXN3Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MTM2Njc5NCwiZXhwIjoyMDY2OTQyNzk0fQ.ng0ST7-V-cDBD0Jc80_0DFWXylzE-gte2I9MCX7qb0Q"
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env file")
        
        self.client: Client = create_client(self.supabase_url, self.supabase_key)
    
    def insert_kl_zone(self, kl_zone_data: Dict) -> Optional[Dict]:
        """Insert a new KL zone into the database (minimal required fields)"""
        try:
            insert_data = {
                'symbol': kl_zone_data['symbol'],
                'kl_type': kl_zone_data['kl_type'],
                'zone_high': float(kl_zone_data['zone_high']),
                'zone_low': float(kl_zone_data['zone_low']),
                'zone_size': float(kl_zone_data['zone_size']),
                'atr_value': float(kl_zone_data['atr']),
                'atr_multiplier': float(kl_zone_data.get('atr_multiplier', 2.0)),
                'candle_label': str(kl_zone_data['candle_label']),
                'time_period': kl_zone_data.get('time_period', 'weekly'),
                'chart_interval': kl_zone_data.get('chart_interval', '1h'),
            }
            response = self.client.table('kl_zones').insert(insert_data).execute()
            if response.data:
                return response.data[0]
            else:
                st.error("No data returned from insert operation")
                logging.error("No data returned from insert operation")
                return None
        except Exception as e:
            st.error(f"Error inserting KL zone: {e}")
            logging.error(f"Error inserting KL zone: {e}")
            return None
    
    def get_kl_zones_for_symbol(self, symbol: str, time_period: str = 'weekly') -> List[Dict]:
        """Retrieve KL zones for a specific symbol and time period"""
        try:
            response = self.client.table('kl_zones').select('*').eq('symbol', symbol).eq('time_period', time_period).order('clicked_datetime', desc=True).execute()
            
            if response.data:
                return response.data
            else:
                return []
                
        except Exception as e:
            st.error(f"Error retrieving KL zones: {e}")
            logging.error(f"Error retrieving KL zones: {e}")
            return []
    
    def get_kl_zones_summary(self, symbol: str, time_period: str = 'weekly') -> pd.DataFrame:
        """Get KL zones summary as a pandas DataFrame"""
        try:
            response = self.client.rpc('get_kl_zones_for_symbol', {
                'p_symbol': symbol,
                'p_time_period': time_period
            }).execute()
            
            if response.data:
                return pd.DataFrame(response.data)
            else:
                return pd.DataFrame()
                
        except Exception as e:
            st.error(f"Error retrieving KL zones summary: {e}")
            logging.error(f"Error retrieving KL zones summary: {e}")
            return pd.DataFrame()
    
    def get_kl_zones_stats(self, symbol: str, time_period: str = 'weekly') -> Dict:
        """Get KL zones statistics for a symbol"""
        try:
            response = self.client.rpc('get_kl_zones_stats', {
                'p_symbol': symbol,
                'p_time_period': time_period
            }).execute()
            
            if response.data:
                return response.data[0]
            else:
                return {
                    'total_zones': 0,
                    'avg_zone_size': 0,
                    'avg_cot_change': 0,
                    'swing_high_count': 0,
                    'swing_low_count': 0,
                    'general_count': 0,
                    'latest_kl_datetime': None
                }
                
        except Exception as e:
            st.error(f"Error retrieving KL zones stats: {e}")
            logging.error(f"Error retrieving KL zones stats: {e}")
            return {}
    
    def delete_kl_zone(self, zone_id: str) -> bool:
        """Delete a KL zone by ID"""
        try:
            response = self.client.table('kl_zones').delete().eq('id', zone_id).execute()
            return len(response.data) > 0
        except Exception as e:
            st.error(f"Error deleting KL zone: {e}")
            logging.error(f"Error deleting KL zone: {e}")
            return False
    
    def delete_kl_zones_for_session(self, session_id: str) -> bool:
        """Delete all KL zones for a specific session"""
        try:
            response = self.client.table('kl_zones').delete().eq('session_id', session_id).execute()
            return len(response.data) > 0
        except Exception as e:
            st.error(f"Error deleting KL zones for session: {e}")
            logging.error(f"Error deleting KL zones for session: {e}")
            return False
    
    def update_kl_zone(self, zone_id: str, update_data: Dict) -> Optional[Dict]:
        """Update a KL zone"""
        try:
            response = self.client.table('kl_zones').update(update_data).eq('id', zone_id).execute()
            
            if response.data:
                return response.data[0]
            else:
                return None
                
        except Exception as e:
            st.error(f"Error updating KL zone: {e}")
            logging.error(f"Error updating KL zone: {e}")
            return None
    
    def get_all_kl_zones(self, limit: int = 100) -> List[Dict]:
        """Get all KL zones with limit"""
        try:
            response = self.client.table('kl_zones').select('*').order('created_at', desc=True).limit(limit).execute()
            
            if response.data:
                return response.data
            else:
                return []
                
        except Exception as e:
            st.error(f"Error retrieving all KL zones: {e}")
            logging.error(f"Error retrieving all KL zones: {e}")
            return []
    
    def search_kl_zones(self, symbol: str = None, kl_type: str = None, time_period: str = None) -> List[Dict]:
        """Search KL zones with filters"""
        try:
            query = self.client.table('kl_zones').select('*')
            
            if symbol:
                query = query.eq('symbol', symbol)
            if kl_type:
                query = query.eq('kl_type', kl_type)
            if time_period:
                query = query.eq('time_period', time_period)
            
            response = query.order('created_at', desc=True).execute()
            
            if response.data:
                return response.data
            else:
                return []
                
        except Exception as e:
            st.error(f"Error searching KL zones: {e}")
            logging.error(f"Error searching KL zones: {e}")
            return []

# Global client instance
_kl_client = None

def get_kl_client() -> SupabaseKLClient:
    """Get or create a global KL client instance"""
    global _kl_client
    if _kl_client is None:
        _kl_client = SupabaseKLClient()
    return _kl_client

def format_kl_zone_for_db(kl_zone: Dict, symbol: str, cot_asset_name: str, time_period: str = 'weekly') -> Dict:
    """Format KL zone data for database insertion (minimal required fields)."""
    return {
        'symbol': symbol,
        'kl_type': kl_zone['kl_type'],
        'zone_high': kl_zone['zone_high'],
        'zone_low': kl_zone['zone_low'],
        'zone_size': kl_zone['zone_size'],
        'atr': kl_zone['atr'],
        'atr_multiplier': 2.0,
        'candle_label': kl_zone['clicked_point'],  # Use clicked_point as candle_label
        'time_period': time_period,
        'chart_interval': '1h',
    } 