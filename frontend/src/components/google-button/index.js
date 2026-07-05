import { useEffect, useRef } from 'react'

const CLIENT_ID = process.env.REACT_APP_GOOGLE_CLIENT_ID

// Официальная кнопка Google Identity Services. GIS-скрипт подключён в
// public/index.html; ждём его загрузки, инициализируем и рендерим кнопку.
const GoogleButton = ({ onGoogleAuth }) => {
  const buttonRef = useRef(null)
  const callbackRef = useRef(onGoogleAuth)
  callbackRef.current = onGoogleAuth

  useEffect(() => {
    if (!CLIENT_ID) { return }

    const renderButton = () => {
      const gis = window.google && window.google.accounts && window.google.accounts.id
      if (!gis || !buttonRef.current) { return false }
      gis.initialize({
        client_id: CLIENT_ID,
        callback: (response) => callbackRef.current(response.credential)
      })
      gis.renderButton(buttonRef.current, {
        theme: 'outline',
        size: 'large',
        text: 'continue_with',
        locale: 'ru',
        width: 280
      })
      return true
    }

    if (renderButton()) { return }
    const intervalId = setInterval(() => {
      if (renderButton()) { clearInterval(intervalId) }
    }, 200)
    return () => clearInterval(intervalId)
  }, [])

  if (!CLIENT_ID) { return null }
  return <div ref={buttonRef} />
}

export default GoogleButton
