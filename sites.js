// sites.js - DESERTAS Stations API
// Returns all monitoring stations with coordinates

const { createClient } = require('@supabase/supabase-js');

exports.handler = async (event, context) => {
  const headers = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type'
  };

  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 204, headers, body: '' };
  }

  try {
    const supabaseUrl = process.env.SUPABASE_URL;
    const supabaseServiceKey = process.env.SUPABASE_SERVICE_KEY;

    if (!supabaseUrl || !supabaseServiceKey) {
      // Return sample data with coordinates
      return {
        statusCode: 200,
        headers,
        body: JSON.stringify(getSampleStations())
      };
    }

    const supabase = createClient(supabaseUrl, supabaseServiceKey);

    // جلب جميع المحطات
    const { data: stations, error } = await supabase
      .from('stations')
      .select('*');

    if (error) throw error;

    if (!stations || stations.length === 0) {
      return {
        statusCode: 200,
        headers,
        body: JSON.stringify(getSampleStations())
      };
    }

    // تنسيق البيانات بشكل صحيح للخريطة
    const formattedStations = stations.map(station => ({
      code: station.station_code,
      name: station.station_name,
      craton: station.craton_code,
      country: station.country,
      region: station.region,
      // تأكد من وجود الإحداثيات
      latitude: station.latitude || getDefaultLat(station.craton_code),
      longitude: station.longitude || getDefaultLng(station.craton_code),
      elevation: station.elevation_m,
      lithology: station.lithology,
      drgis_current: station.drgis_current || 0,
      alert_level_current: station.alert_level_current || 'BACKGROUND',
      lead_time_days: station.lead_time_days
    }));

    return {
      statusCode: 200,
      headers,
      body: JSON.stringify(formattedStations)
    };

  } catch (error) {
    console.error('Error in stations function:', error);
    return {
      statusCode: 200,
      headers,
      body: JSON.stringify(getSampleStations())
    };
  }
};

// إحداثيات افتراضية لكل كراتون (إذا لم تكن موجودة في قاعدة البيانات)
function getDefaultLat(craton) {
  const coords = {
    'SAH': 31.2500,  // شمال إفريقيا
    'ARA': 28.4000,  // الجزيرة العربية
    'KAA': -26.2000, // جنوب إفريقيا
    'YIL': -30.7000, // غرب أستراليا
    'ATA': -23.3000, // أمريكا الجنوبية
    'TAR': 37.1000,  // آسيا الوسطى
    'SCA': 69.6000   // شمال أوروبا
  };
  return coords[craton] || 0;
}

function getDefaultLng(craton) {
  const coords = {
    'SAH': -7.5000,   // شمال إفريقيا
    'ARA': 36.5000,   // الجزيرة العربية
    'KAA': 28.0000,   // جنوب إفريقيا
    'YIL': 121.4000,  // غرب أستراليا
    'ATA': -67.7000,  // أمريكا الجنوبية
    'TAR': 79.9000,   // آسيا الوسطى
    'SCA': 19.0000    // شمال أوروبا
  };
  return coords[craton] || 0;
}

function getSampleStations() {
  return [
    {
      code: 'DES-MA-02',
      name: 'High Atlas Station',
      craton: 'SAH',
      country: 'Morocco',
      region: 'Marrakech-Safi',
      latitude: 31.2500,
      longitude: -7.5000,
      elevation: 1450,
      lithology: 'Pan-African granite gneiss',
      drgis_current: 0.596,
      alert_level_current: 'EMERGENCY',
      lead_time_days: 58
    },
    {
      code: 'DES-SA-01',
      name: 'Tabuk Station',
      craton: 'ARA',
      country: 'Saudi Arabia',
      region: 'Tabuk Province',
      latitude: 28.4000,
      longitude: 36.5000,
      elevation: 760,
      lithology: 'Neoproterozoic tonalite',
      drgis_current: 0.412,
      alert_level_current: 'ALERT',
      lead_time_days: 63
    },
    {
      code: 'DES-CL-03',
      name: 'Lascar Station',
      craton: 'ATA',
      country: 'Chile',
      region: 'Antofagasta',
      latitude: -23.3000,
      longitude: -67.7000,
      elevation: 4100,
      lithology: 'Volcanic basement',
      drgis_current: 0.338,
      alert_level_current: 'WATCH',
      lead_time_days: 71
    },
    {
      code: 'DES-SC-01',
      name: 'Tromsø Station',
      craton: 'SCA',
      country: 'Norway',
      region: 'Troms',
      latitude: 69.6000,
      longitude: 19.0000,
      elevation: 150,
      lithology: 'Archean gneiss',
      drgis_current: 0.623,
      alert_level_current: 'CRITICAL',
      lead_time_days: 29
    },
    {
      code: 'DES-TA-02',
      name: 'Hotan Station',
      craton: 'TAR',
      country: 'China',
      region: 'Xinjiang',
      latitude: 37.1000,
      longitude: 79.9000,
      elevation: 1370,
      lithology: 'Precambrian granite',
      drgis_current: 0.512,
      alert_level_current: 'EMERGENCY',
      lead_time_days: 52
    },
    {
      code: 'DES-KA-04',
      name: 'Johannesburg Station',
      craton: 'KAA',
      country: 'South Africa',
      region: 'Gauteng',
      latitude: -26.2000,
      longitude: 28.0000,
      elevation: 1650,
      lithology: 'Witwatersrand quartzite',
      drgis_current: 0.445,
      alert_level_current: 'ALERT',
      lead_time_days: 44
    },
    {
      code: 'DES-AU-06',
      name: 'Wiluna Station',
      craton: 'YIL',
      country: 'Australia',
      region: 'Western Australia',
      latitude: -26.5000,
      longitude: 120.1000,
      elevation: 480,
      lithology: 'Archean granite',
      drgis_current: 0.284,
      alert_level_current: 'WATCH',
      lead_time_days: 38
    }
  ];
}
