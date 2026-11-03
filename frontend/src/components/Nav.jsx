import { Link } from "../router.jsx";

export default function Nav() {
  return (
    <header className="row">
      <Link to="/" className="brand"><h1>Rewind</h1></Link>
      <nav className="row">
        <Link to="/amigos">Amigos</Link>
        <Link to="/conta">Conta</Link>
      </nav>
    </header>
  );
}
