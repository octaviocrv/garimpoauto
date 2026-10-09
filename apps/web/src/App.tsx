import { ArrowRight, ChartNoAxesCombined, Search, SlidersHorizontal } from 'lucide-react'
import './App.css'
import { Hero } from './components/Hero'

function App() {
  return (
    <div className="site-shell">
      <main>
        <Hero />

        <section className="steps-section" id="como-funciona" aria-labelledby="steps-title">
          <div className="section-heading">
            <p className="eyebrow">Direto ao ponto</p>
            <h2 id="steps-title">Menos aba aberta. Mais carro na tela.</h2>
          </div>
          <div className="steps-grid">
            <article className="step-card"><span className="step-number">01</span><Search size={28} aria-hidden="true" /><h3>Você procura</h3><p>Informe o carro que você quer encontrar e os critérios que fazem sentido pro seu estoque.</p></article>
            <article className="step-card"><span className="step-number">02</span><SlidersHorizontal size={28} aria-hidden="true" /><h3>A gente organiza</h3><p>Os anúncios chegam padronizados para você bater o olho em ano, km, preço e origem.</p></article>
            <article className="step-card"><span className="step-number">03</span><ChartNoAxesCombined size={28} aria-hidden="true" /><h3>Você compara</h3><p>O foco é facilitar a escolha do carro que vale sua atenção, sem enrolação.</p></article>
          </div>
        </section>

        <section className="focus-section" id="foco" aria-labelledby="focus-title">
          <div><p className="eyebrow">Agora</p><h2 id="focus-title">Primeiro, fazer a busca funcionar bem.</h2></div>
          <p>A primeira etapa é consultar uma fonte de ponta a ponta, tratar os dados e mostrar um resultado simples. Depois entram as outras fontes e os filtros.</p>
        </section>

        <section className="cta-section" id="acompanhar" aria-labelledby="cta-title">
          <div><p className="eyebrow eyebrow-light">Garimpo Auto</p><h2 id="cta-title">Estamos colocando a primeira busca na rua.</h2><p>Esta página é o ponto de partida. A próxima tela será a busca de carros.</p></div>
          <a className="button button-light" href="mailto:contato@garimpoauto.local">Quero acompanhar <ArrowRight size={18} aria-hidden="true" /></a>
        </section>
      </main>

      <footer className="footer"><span>Garimpo Auto</span><span>Um lugar só pra achar carro e bom negócio.</span></footer>
    </div>
  )
}

export default App
