import { ArrowRight, ChartNoAxesCombined, Search, SlidersHorizontal } from 'lucide-react'
import './App.css'

function App() {
  return (
    <div className="site-shell">
      <header className="topbar">
        <a className="brand" href="#inicio" aria-label="Garimpo Auto, ir para o início">
          <span className="brand-mark"><img src="/mascot/han-profile.jpeg" alt="" /></span>
          <span>Garimpo Auto</span>
        </a>
        <nav className="nav-links" aria-label="Navegação principal">
          <a href="#como-funciona">Como funciona</a>
          <a href="#foco">O que estamos fazendo</a>
        </nav>
        <a className="topbar-action" href="#acompanhar">Acompanhar</a>
      </header>

      <main>
        <section className="hero" id="inicio">
          <div className="hero-copy">
            <p className="eyebrow">Busca de carros usados em um só lugar</p>
            <h1>Garimpo Auto</h1>
            <p className="hero-lede">Ache carros sem abrir vários sites. A gente reúne os anúncios e deixa a comparação mais clara pra você encontrar bom negócio.</p>
            <div className="hero-actions">
              <a className="button button-primary" href="#como-funciona">Ver como funciona <ArrowRight size={18} aria-hidden="true" /></a>
              <a className="button button-secondary" href="#foco">Acompanhar construção</a>
            </div>
            <p className="hero-note">Primeira versão em desenvolvimento para revendedores da região de BH e Contagem.</p>
          </div>
          <div className="hero-visual" aria-label="Han, mascote do Garimpo Auto">
            <div className="visual-frame">
              <span className="frame-outline frame-outline-one" />
              <span className="frame-outline frame-outline-two" />
              <img src="/mascot/han-fullbody.jpeg" alt="Han, mascote do Garimpo Auto" />
            </div>
          </div>
        </section>

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
