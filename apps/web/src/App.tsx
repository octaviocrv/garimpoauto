import { useEffect, useState } from 'react'
import './App.css'
import { PaginaBusca } from './busca/PaginaBusca'
import { Hero } from './components/Hero'
import { ConsoleCta } from './components/sections/ConsoleCta'
import { FocusNow } from './components/sections/FocusNow'
import { Steps } from './components/sections/Steps'

// Rota por hash: #/buscar abre a tela de busca, qualquer outra coisa é a home.
function useNaBusca() {
  const [hash, setHash] = useState(window.location.hash)
  useEffect(() => {
    const aoMudar = () => { setHash(window.location.hash); window.scrollTo(0, 0) }
    window.addEventListener('hashchange', aoMudar)
    return () => window.removeEventListener('hashchange', aoMudar)
  }, [])
  return hash.startsWith('#/buscar')
}

function App() {
  if (useNaBusca()) return <PaginaBusca />
  return (
    <div className="site-shell">
      <main>
        <Hero />
        <Steps />
        <FocusNow />
        <ConsoleCta />
      </main>

      <footer className="footer">
        <div className="footer-inner">
          <span className="footer-brand">
            <span className="font-jp" aria-hidden="true">
              ガリンボ
            </span>
            Garimpo Auto
          </span>
          <span>Um lugar só pra achar carro e bom negócio.</span>
        </div>
      </footer>
    </div>
  )
}

export default App
