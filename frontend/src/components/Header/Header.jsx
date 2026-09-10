import { NavLink } from 'react-router-dom'

import './Header.css'

function Header() {
  return (
    <header className="header">
      <div className="header-brand">
        <h1>CCTV AI Surveillance</h1>
        <span>Intelligent monitoring & incident management</span>
      </div>

      <nav className="header-nav">
        <NavLink
          to="/"
          className={({ isActive }) =>
            isActive ? 'nav-link active' : 'nav-link'
          }
        >
          Dashboard
        </NavLink>

        <NavLink
          to="/incidents"
          className={({ isActive }) =>
            isActive ? 'nav-link active' : 'nav-link'
          }
        >
          Incidents
        </NavLink>

        <NavLink
          to="/recorded-analysis"
          className={({ isActive }) =>
            isActive ? 'nav-link active' : 'nav-link'
          }
        >
          Recorded Analysis
        </NavLink>
      </nav>
    </header>
  )
}

export default Header
