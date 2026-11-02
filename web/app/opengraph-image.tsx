import { ImageResponse } from 'next/og'

export const alt = 'Sky Alerts — What the sky did last night'
export const size = { width: 1200, height: 630 }
export const contentType = 'image/png'

export default function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          padding: '72px 84px',
          background: 'linear-gradient(135deg, #070b16 0%, #0f1a36 55%, #17223a 100%)',
          color: '#eef1f7',
          fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto, sans-serif',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '18px',
          }}
        >
          <svg viewBox="0 0 24 24" width="52" height="52">
            <path fill="#ffd36e" d="M12 2l2.2 6.8L21 11l-6.8 2.2L12 20l-2.2-6.8L3 11l6.8-2.2z" />
          </svg>
          <span
            style={{
              fontSize: 44,
              fontWeight: 700,
              letterSpacing: '-0.02em',
              color: '#eef1f7',
            }}
          >
            Sky Alerts
          </span>
        </div>

        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '20px',
          }}
        >
          <div
            style={{
              fontSize: 72,
              fontWeight: 700,
              lineHeight: 1.1,
              letterSpacing: '-0.03em',
              color: '#eef1f7',
            }}
          >
            What the sky did last night
          </div>
          <div
            style={{
              fontSize: 30,
              lineHeight: 1.4,
              color: '#b7bfd0',
            }}
          >
            Supernovae, variable stars and cosmic transients from Rubin (LSST) and ZTF via ALeRCE.
          </div>
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            paddingTop: '28px',
            borderTop: '1px solid rgba(255, 255, 255, 0.12)',
            fontSize: 26,
            color: '#9cc1ff',
          }}
        >
          <span>sky.henseler.app</span>
          <span style={{ color: '#8b94a8', fontSize: 22 }}>Vera C. Rubin Observatory · ZTF · ALeRCE</span>
        </div>
      </div>
    ),
    { ...size },
  )
}
