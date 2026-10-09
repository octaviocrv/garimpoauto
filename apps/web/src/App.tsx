import './App.css'
import { Hero } from './components/Hero'
import { ConsoleCta } from './components/sections/ConsoleCta'
import { FocusNow } from './components/sections/FocusNow'
import { Steps } from './components/sections/Steps'

function App() {
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
