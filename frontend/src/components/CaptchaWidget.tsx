import React, { useState, useEffect, useRef } from 'react';
import ReCAPTCHA from 'react-google-recaptcha';
import { api } from '../services/api';

export interface CaptchaResult {
  token: string;
  id?: string;
}

interface CaptchaWidgetProps {
  onVerify: (result: CaptchaResult) => void;
}

export const CaptchaWidget: React.FC<CaptchaWidgetProps> = ({ onVerify }) => {
  const [config, setConfig] = useState<{ captcha_type: string; recaptcha_site_key: string | null } | null>(null);
  const [customData, setCustomData] = useState<{ id: string; image: string } | null>(null);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(true);
  const recaptchaRef = useRef<ReCAPTCHA>(null);

  const fetchConfig = async () => {
    try {
      const res = await api.get('/api/v1/auth/config');
      if (res.success) {
        setConfig(res.data);
      }
    } catch (err) {
      console.error('Failed to load captcha config', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchCustomCaptcha = async () => {
    try {
      const res = await api.get('/api/v1/auth/captcha');
      if (res.success) {
        setCustomData({ id: res.data.captcha_id, image: res.data.image_data });
      }
    } catch (err) {
      console.error('Failed to load custom captcha', err);
    }
  };

  useEffect(() => {
    fetchConfig();
  }, []);

  useEffect(() => {
    if (config?.captcha_type === 'custom') {
      fetchCustomCaptcha();
    }
  }, [config]);

  if (loading) return <div>Loading security check...</div>;

  if (config?.captcha_type === 'none' || !config?.captcha_type) {
    return null; // No captcha required
  }

  if (config.captcha_type === 'google' && config.recaptcha_site_key) {
    return (
      <div className="mb-4 flex justify-center">
        <ReCAPTCHA
          ref={recaptchaRef}
          sitekey={config.recaptcha_site_key}
          onChange={(token) => {
            if (token) onVerify({ token });
          }}
        />
      </div>
    );
  }

  if (config.captcha_type === 'custom' && customData) {
    return (
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-1">Security Check</label>
        <div className="flex items-center space-x-4">
          <div className="bg-gray-100 p-2 rounded border cursor-pointer" onClick={fetchCustomCaptcha} title="Click to refresh">
            <img src={customData.image} alt="CAPTCHA" className="h-10" />
          </div>
          <input
            type="text"
            className="flex-1 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm px-3 py-2 border"
            placeholder="Enter text"
            value={inputValue}
            onChange={(e) => {
              setInputValue(e.target.value);
              if (e.target.value.length === 5) {
                onVerify({ token: e.target.value, id: customData.id });
              }
            }}
            onBlur={(e) => {
               onVerify({ token: e.target.value, id: customData.id });
            }}
            required
            maxLength={5}
          />
        </div>
      </div>
    );
  }

  return null;
};
