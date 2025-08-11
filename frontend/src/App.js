import React, { useState, useEffect } from 'react';

const PITCH_COLORS = {
  'FF': '#D62828', 'SI': '#F77F00', 'FC': '#7F4F24', 'CH': '#43AA8B',
  'FS': '#3A9D9A', 'FO': '#4ECDC4', 'SC': '#90BE6D', 'CU': '#48CAE4',
  'KC': '#6930C3', 'CS': '#3A0CA3', 'SL': '#F9C74F', 'ST': '#F8961E', 'SV': '#90A0C0'
};

function App() {
  const [selectedDate, setSelectedDate] = useState(() => {
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    return yesterday.toISOString().split('T')[0];
  });
  const [selectedCatcher, setSelectedCatcher] = useState(null);
  const [catchers, setCatchers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [plotLoading, setPlotLoading] = useState(false);
  const [plotImage, setPlotImage] = useState(null);

  useEffect(() => {
    fetchCatcherData(selectedDate);
  }, [selectedDate]);

  const fetchCatcherData = async (date) => {
    setLoading(true);
    setError(null);
    try {
     const response = await fetch(`https://framing-summary-production.up.railway.app/api/statcast/catchers?date=${date}`);
      const data = await response.json();
      
      if (response.ok) {
        setCatchers(data);
        if (data.length === 0) {
          setError('No catcher data found for this date. Try a different date when MLB games were played.');
        }
      } else {
        setError(data.error || 'Failed to fetch data');
        setCatchers([]);
      }
    } catch (error) {
      console.error('Error fetching catcher data:', error);
      setError('Failed to connect to backend. Make sure the Flask server is running.');
      setCatchers([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchGameSummaryPlot = async (catcher) => {
    setPlotLoading(true);
    try {
     const response = await fetch(`https://framing-summary-production.up.railway.app/api/plot/${catcher.id}/${catcher.game_pk}?date=${selectedDate}`);
      const data = await response.json();
      
      if (response.ok && data.image) {
        setPlotImage(data.image);
      } else {
        setError('Failed to generate plot: ' + (data.error || 'Unknown error'));
      }
    } catch (error) {
      console.error('Error fetching plot:', error);
      setError('Failed to generate plot');
    } finally {
      setPlotLoading(false);
    }
  };

  const handleCatcherClick = (catcher) => {
    setSelectedCatcher(catcher);
    setPlotImage(null);
    fetchGameSummaryPlot(catcher);
  };

  const getHeadshotUrl = (playerId) => {
    return `https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/${playerId}/headshot/67/current`;
  };

  const formatDateForDisplay = (dateString) => {
    // Create date object and ensure it's interpreted as local time
    const [year, month, day] = dateString.split('-');
    const date = new Date(year, month - 1, day); // month is 0-indexed
    
    return date.toLocaleDateString('en-US', { 
      weekday: 'long', 
      year: 'numeric', 
      month: 'long', 
      day: 'numeric' 
    });
  };

  // Color grading functions - RED = BEST, BLUE = WORST
  const getPerformanceColor = (value, values, reverseScale = false) => {
    if (values.length === 0) return { bg: '#374151', border: '#4b5563', text: '#9ca3af' };
    
    const sortedValues = [...values].sort((a, b) => reverseScale ? b - a : a - b);
    const min = sortedValues[0];
    const max = sortedValues[sortedValues.length - 1];
    
    if (min === max) return { bg: '#374151', border: '#4b5563', text: '#9ca3af' };
    
    const percentile = (value - min) / (max - min);
    
    // Color scale from blue (worst) to red (best)
    if (percentile >= 0.8) {
      return { bg: '#7f1d1d', border: '#dc2626', text: '#fca5a5' }; // Best - Dark red
    } else if (percentile >= 0.6) {
      return { bg: '#92400e', border: '#d97706', text: '#fbbf24' }; // Good - Orange-red
    } else if (percentile >= 0.4) {
      return { bg: '#374151', border: '#4b5563', text: '#9ca3af' }; // Average - Gray
    } else if (percentile >= 0.2) {
      return { bg: '#1e3a8a', border: '#2563eb', text: '#93c5fd' }; // Poor - Blue
    } else {
      return { bg: '#1e1b4b', border: '#3730a3', text: '#a5b4fc' }; // Worst - Dark blue
    }
  };

  const getMetricColors = (catchers) => {
    const csRates = catchers.map(c => c.called_strike_rate);
    const extraStrikes = catchers.map(c => c.extra_strikes);
    const lostStrikes = catchers.map(c => c.lost_strikes);
    const netImpacts = catchers.map(c => c.extra_strikes - c.lost_strikes);

    return {
      csRates,
      extraStrikes,
      lostStrikes: lostStrikes.map(l => -l), // Reverse scale - fewer lost strikes is better
      netImpacts
    };
  };

  const CatcherCard = ({ catcher, allCatchers }) => {
    const metrics = getMetricColors(allCatchers);
    
    const csColor = getPerformanceColor(catcher.called_strike_rate, metrics.csRates);
    const extraColor = getPerformanceColor(catcher.extra_strikes, metrics.extraStrikes);
    const lostColor = getPerformanceColor(-catcher.lost_strikes, metrics.lostStrikes);
    const netColor = getPerformanceColor(catcher.extra_strikes - catcher.lost_strikes, metrics.netImpacts);

    return (
      <div
        style={{
          backgroundColor: '#1f2937',
          borderRadius: '8px',
          boxShadow: '0 4px 6px rgba(0,0,0,0.3)',
          padding: '20px',
          cursor: 'pointer',
          borderLeft: '4px solid #3b82f6',
          transition: 'transform 0.2s, box-shadow 0.2s',
          border: '1px solid #374151'
        }}
        onClick={() => handleCatcherClick(catcher)}
        onMouseEnter={(e) => {
          e.currentTarget.style.transform = 'translateY(-2px)';
          e.currentTarget.style.boxShadow = '0 8px 25px rgba(0,0,0,0.4)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.transform = 'translateY(0)';
          e.currentTarget.style.boxShadow = '0 4px 6px rgba(0,0,0,0.3)';
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '15px' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 'bold', color: '#f9fafb' }}>{catcher.player_name}</h3>
            <p style={{ margin: '2px 0 0 0', color: '#9ca3af' }}>{catcher.matchup}</p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <img
              src={getHeadshotUrl(catcher.id)}
              alt={catcher.player_name}
              style={{
                width: '50px',
                height: '50px',
                borderRadius: '50%',
                border: '2px solid #374151',
                backgroundColor: '#374151'
              }}
              onError={(e) => {
                e.target.style.display = 'none';
              }}
            />
          </div>
        </div>
        
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
          <div style={{ backgroundColor: csColor.bg, padding: '10px', borderRadius: '6px', border: `1px solid ${csColor.border}` }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', marginBottom: '5px' }}>
              <span style={{ fontSize: '12px', fontWeight: '500', color: csColor.text }}>Shadow Zone CS%</span>
            </div>
            <p style={{ margin: 0, fontSize: '16px', fontWeight: 'bold', color: csColor.text }}>
              {(catcher.called_strike_rate * 100).toFixed(1)}%
            </p>
            <p style={{ margin: '2px 0 0 0', fontSize: '10px', color: csColor.text, opacity: 0.8 }}>
              ({catcher.shadow_zone_pitches} borderline pitches)
            </p>
          </div>
          
          <div style={{ backgroundColor: extraColor.bg, padding: '10px', borderRadius: '6px', border: `1px solid ${extraColor.border}` }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', marginBottom: '5px' }}>
              <span style={{ fontSize: '12px', fontWeight: '500', color: extraColor.text }}>Extra Strikes</span>
            </div>
            <p style={{ margin: 0, fontSize: '16px', fontWeight: 'bold', color: extraColor.text }}>
              +{catcher.extra_strikes}
            </p>
          </div>
          
          <div style={{ backgroundColor: lostColor.bg, padding: '10px', borderRadius: '6px', border: `1px solid ${lostColor.border}` }}>
            <span style={{ fontSize: '12px', fontWeight: '500', color: lostColor.text }}>Lost Strikes</span>
            <p style={{ margin: '5px 0 0 0', fontSize: '16px', fontWeight: 'bold', color: lostColor.text }}>
              -{catcher.lost_strikes}
            </p>
          </div>
          
          <div style={{ backgroundColor: netColor.bg, padding: '10px', borderRadius: '6px', border: `1px solid ${netColor.border}` }}>
            <span style={{ fontSize: '12px', fontWeight: '500', color: netColor.text }}>Net Impact</span>
            <p style={{ margin: '5px 0 0 0', fontSize: '16px', fontWeight: 'bold', color: netColor.text }}>
              +{catcher.extra_strikes - catcher.lost_strikes}
            </p>
          </div>
        </div>
        
        <div style={{ 
          marginTop: '15px', 
          padding: '8px', 
          backgroundColor: '#374151', 
          borderRadius: '4px', 
          textAlign: 'center',
          fontSize: '12px',
          color: '#9ca3af',
          fontWeight: '500'
        }}>
          Click to view game summary plot
        </div>
      </div>
    );
  };

  if (selectedCatcher) {
    const metrics = getMetricColors(catchers);
    const csColor = getPerformanceColor(selectedCatcher.called_strike_rate, metrics.csRates);
    const extraColor = getPerformanceColor(selectedCatcher.extra_strikes, metrics.extraStrikes);
    const lostColor = getPerformanceColor(-selectedCatcher.lost_strikes, metrics.lostStrikes);
    const netColor = getPerformanceColor(selectedCatcher.extra_strikes - selectedCatcher.lost_strikes, metrics.netImpacts);

    return (
      <div style={{ minHeight: '100vh', backgroundColor: '#111827', padding: '20px' }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
          <button
            onClick={() => {
              setSelectedCatcher(null);
              setPlotImage(null);
            }}
            style={{
              marginBottom: '20px',
              padding: '10px 20px',
              backgroundColor: '#3b82f6',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: '500'
            }}
          >
            ← Back to Dashboard
          </button>
          
          <div style={{
            backgroundColor: '#1f2937',
            borderRadius: '8px',
            boxShadow: '0 4px 6px rgba(0,0,0,0.3)',
            padding: '30px',
            marginBottom: '20px',
            border: '1px solid #374151'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
              <div>
                <h2 style={{ margin: '0 0 10px 0', fontSize: '24px', fontWeight: 'bold', color: '#f9fafb' }}>
                  {selectedCatcher.player_name} - Game Summary
                </h2>
                <p style={{ margin: '0', color: '#9ca3af' }}>
                  {selectedCatcher.matchup} • {selectedCatcher.date}
                </p>
              </div>
              <img
                src={getHeadshotUrl(selectedCatcher.id)}
                alt={selectedCatcher.player_name}
                style={{
                  width: '80px',
                  height: '80px',
                  borderRadius: '50%',
                  border: '3px solid #374151',
                  backgroundColor: '#374151'
                }}
                onError={(e) => {
                  e.target.style.display = 'none';
                }}
              />
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '20px' }}>
              <div style={{ textAlign: 'center' }}>
                <p style={{ margin: 0, fontSize: '28px', fontWeight: 'bold', color: csColor.text }}>
                  {(selectedCatcher.called_strike_rate * 100).toFixed(1)}%
                </p>
                <p style={{ margin: '5px 0 0 0', fontSize: '14px', color: '#9ca3af' }}>Shadow Zone CS%</p>
                <p style={{ margin: '2px 0 0 0', fontSize: '12px', color: '#6b7280' }}>
                  ({selectedCatcher.shadow_zone_pitches} borderline)
                </p>
              </div>
              <div style={{ textAlign: 'center' }}>
                <p style={{ margin: 0, fontSize: '28px', fontWeight: 'bold', color: extraColor.text }}>
                  +{selectedCatcher.extra_strikes}
                </p>
                <p style={{ margin: '5px 0 0 0', fontSize: '14px', color: '#9ca3af' }}>Extra Strikes</p>
              </div>
              <div style={{ textAlign: 'center' }}>
                <p style={{ margin: 0, fontSize: '28px', fontWeight: 'bold', color: lostColor.text }}>
                  -{selectedCatcher.lost_strikes}
                </p>
                <p style={{ margin: '5px 0 0 0', fontSize: '14px', color: '#9ca3af' }}>Lost Strikes</p>
              </div>
              <div style={{ textAlign: 'center' }}>
                <p style={{ margin: 0, fontSize: '28px', fontWeight: 'bold', color: netColor.text }}>
                  +{selectedCatcher.extra_strikes - selectedCatcher.lost_strikes}
                </p>
                <p style={{ margin: '5px 0 0 0', fontSize: '14px', color: '#9ca3af' }}>Net Impact</p>
              </div>
            </div>
          </div>
          
          {plotLoading && (
            <div style={{ textAlign: 'center', padding: '50px 0' }}>
              <div style={{
                width: '32px',
                height: '32px',
                border: '3px solid #374151',
                borderTop: '3px solid #3b82f6',
                borderRadius: '50%',
                animation: 'spin 1s linear infinite',
                margin: '0 auto 10px'
              }}></div>
              <p style={{ color: '#9ca3af' }}>Generating your gameday summary plot...</p>
            </div>
          )}
          
          {plotImage && (
            <div style={{
              backgroundColor: '#1f2937',
              borderRadius: '8px',
              boxShadow: '0 4px 6px rgba(0,0,0,0.3)',
              padding: '20px',
              border: '1px solid #374151'
            }}>
              <h3 style={{ margin: '0 0 20px 0', fontSize: '20px', fontWeight: 'bold', color: '#f9fafb' }}>
                Gameday Summary Plot
              </h3>
              <img 
                src={plotImage} 
                alt="Gameday summary plot" 
                style={{ 
                  width: '100%', 
                  maxWidth: '800px', 
                  height: 'auto',
                  borderRadius: '8px',
                  display: 'block',
                  margin: '0 auto'
                }}
              />
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#111827' }}>
      <header style={{ 
        backgroundColor: '#1f2937', 
        padding: '20px', 
        borderBottom: '1px solid #374151',
        boxShadow: '0 2px 4px rgba(0,0,0,0.3)'
      }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h1 style={{ margin: 0, fontSize: '24px', fontWeight: 'bold', color: '#f9fafb' }}>Daily Framing Summary Dashboard</h1>
            <p style={{ margin: '5px 0 0 0', color: '#9ca3af', fontSize: '14px' }}>Built by Kick Dirt Baseball with Statcast Data</p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <input
              type="date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              style={{
                padding: '8px 12px',
                border: '1px solid #374151',
                borderRadius: '4px',
                fontSize: '14px',
                backgroundColor: '#374151',
                color: '#f9fafb'
              }}
            />
          </div>
        </div>
      </header>

      <main style={{ maxWidth: '1200px', margin: '0 auto', padding: '20px' }}>
        <div style={{ marginBottom: '20px' }}>
          <h2 style={{ fontSize: '20px', fontWeight: '600', marginBottom: '5px', color: '#f9fafb' }}>
            Catchers - {formatDateForDisplay(selectedDate)}
          </h2>
          <p style={{ color: '#9ca3af' }}>{catchers.length} catchers with called pitch data</p>
        </div>

        {error && (
          <div style={{
            backgroundColor: '#7f1d1d',
            border: '1px solid #ef4444',
            borderRadius: '8px',
            padding: '16px',
            marginBottom: '20px'
          }}>
            <p style={{ color: '#fca5a5', margin: 0 }}>{error}</p>
          </div>
        )}

        {loading ? (
          <div style={{ textAlign: 'center', padding: '50px 0' }}>
            <div style={{
              width: '32px',
              height: '32px',
              border: '3px solid #374151',
              borderTop: '3px solid #3b82f6',
              borderRadius: '50%',
              animation: 'spin 1s linear infinite',
              margin: '0 auto 10px'
            }}></div>
            <p style={{ color: '#9ca3af' }}>Loading Statcast data...</p>
            <p style={{ color: '#6b7280', fontSize: '12px' }}>This may take 30-60 seconds for the first request</p>
          </div>
        ) : (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))',
            gap: '20px'
          }}>
            {catchers.map(catcher => (
              <CatcherCard key={`${catcher.id}-${catcher.game_pk}`} catcher={catcher} allCatchers={catchers} />
            ))}
          </div>
        )}

        {!loading && catchers.length === 0 && !error && (
          <div style={{ textAlign: 'center', padding: '50px 0' }}>
            <p style={{ fontSize: '18px', color: '#9ca3af' }}>No catcher data found for this date.</p>
            <p style={{ color: '#6b7280' }}>Try selecting a different date when MLB games were played.</p>
            <p style={{ fontSize: '12px', color: '#6b7280', marginTop: '10px' }}>
              Note: Data is typically available for dates from March through October.
            </p>
          </div>
        )}
      </main>

      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

export default App;