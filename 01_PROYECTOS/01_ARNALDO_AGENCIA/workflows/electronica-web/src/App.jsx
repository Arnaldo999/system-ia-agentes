import React, { useState, useEffect } from 'react';
import { ShoppingCart, Smartphone, Laptop, Zap, MessageCircle, AlertCircle } from 'lucide-react';

// Estos datos se mostrarán solo si falla la conexión a Airtable o mientras carga.
const fallbackProducts = [
    {
        id: 1,
        name: "MacBook Pro M3 Max",
        description: "La laptop más potente de Apple para profesionales creativos.",
        price: 3499,
        image: "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?auto=format&fit=crop&q=80&w=800",
        category: "Laptops"
    }
];

function App() {
    const [products, setProducts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const whatsappNumber = "5493764815689"; // Número de WhatsApp del bot
    const buildWhatsAppLink = (message) => `https://wa.me/${whatsappNumber}?text=${encodeURIComponent(message)}`;

    useEffect(() => {
        const fetchBackendData = async () => {
            try {
                // LLamada a nuestro propio backend (FastAPI)
                const response = await fetch('https://system-ia-agentes.onrender.com/comercio/catalogo');
                if (!response.ok) {
                    throw new Error('Error al obtener datos del servidor');
                }

                const data = await response.json();

                // Mapear los datos que devuelve el JSON de FastAPI al formato del componente
                const formattedProducts = data.productos.map(prod => ({
                    id: prod.id,
                    name: prod.nombre,
                    description: prod.descripcion,
                    price: prod.precio,
                    category: prod.categoria,
                    image: prod.imagen || "https://images.unsplash.com/photo-1542204165-65bf26472b9b?auto=format&fit=crop&q=80&w=800"
                }));

                setProducts(formattedProducts);
            } catch (err) {
                console.error("Error fetching from Backend:", err);
                setError("No pudimos cargar el catálogo actualizado. Mostrando demo offline.");
                setProducts(fallbackProducts);
            } finally {
                setLoading(false);
            }
        };

        fetchBackendData();
    }, []);

    return (
        <div className="app-wrapper">
            <nav className="navbar">
                <div className="container navbar-container">
                    <div className="brand"><a href="#inicio">TechStore</a></div>
                    <div className="nav-links">
                        <a href="#inicio">Inicio</a>
                        <a href="#productos">Productos</a>
                        <a href="#nosotros">Quiénes Somos</a>
                        <a href="#contacto">Contacto</a>
                    </div>
                </div>
            </nav>

            <section id="inicio" className="hero">
                <div className="container animate-fade-in">
                    <h1>Tecnología que te <span className="brand">impulsa</span></h1>
                    <p>Encuentra los dispositivos de última generación al mejor precio. Descubrí una experiencia nueva, comprá online y retira hoy mismo en nuestro local.</p>
                    <a href={buildWhatsAppLink("Hola! Me gustaría hablar con un asesor para que me recomiende un producto.")} className="btn btn-primary" target="_blank" rel="noopener noreferrer">
                        <MessageCircle size={20} />
                        Hablar con un asesor IA
                    </a>
                </div>
            </section>

            <main className="container animate-fade-in">
                <section id="productos" className="products">
                    <h2>Catálogo Destacado</h2>

                    {loading && <p style={{ textAlign: "center", padding: "2rem" }}>Cargando catálogo en vivo...</p>}

                    {error && (
                        <div style={{ backgroundColor: "rgba(239, 68, 68, 0.1)", color: "#ef4444", padding: "1rem", borderRadius: "0.5rem", marginBottom: "1rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                            <AlertCircle size={20} />
                            {error}
                        </div>
                    )}

                    {!loading && products.length === 0 && (
                        <p style={{ textAlign: "center", padding: "2rem" }}>No hay productos disponibles por el momento.</p>
                    )}

                    <div className="products-grid">
                        {products.map((product, index) => (
                            <div key={product.id} className="product-card animate-fade-in" style={{ animationDelay: `${index * 0.1}s` }}>
                                <div className="product-image-container">
                                    <img src={product.image} alt={product.name} loading="lazy" />
                                </div>
                                <div className="product-info">
                                    <h3 className="product-title">{product.name}</h3>
                                    <p className="product-description">{product.description}</p>
                                    <div className="product-footer">
                                        <span className="product-price">${product.price.toLocaleString('es-AR')}</span>
                                    </div>
                                    <a
                                        href={buildWhatsAppLink(`Hola, me interesa el producto: ${product.name} ($${product.price.toLocaleString('es-AR')}).`)}
                                        className="btn btn-whatsapp"
                                        target="_blank"
                                        rel="noopener noreferrer"
                                    >
                                        <ShoppingCart size={18} /> Comprar por WhatsApp
                                    </a>
                                </div>
                            </div>
                        ))}
                    </div>
                </section>

                <section id="nosotros" className="about-section">
                    <h2>Quiénes Somos</h2>
                    <div className="about-content">
                        <p>
                            En <strong>TechStore</strong> somos apasionados por la tecnología. Nacimos con el objetivo de acercar los mejores dispositivos electrónicos a nuestra comunidad, brindando asesoramiento experto y transparente.
                        </p>
                        <p>
                            Nuestro equipo está capacitado para entender tus necesidades y recomendarte exactamente lo que buscas, ya sea de forma presencial en nuestro local o a través de nuestro Asesor de Inteligencia Artificial disponible las 24 horas por WhatsApp.
                        </p>
                    </div>
                </section>
            </main>

            <footer id="contacto">
                <div className="container footer-container">
                    <div className="footer-section">
                        <h3>Contacto</h3>
                        <p>📍 Av. Corrientes 1234, CABA</p>
                        <p>🕒 Lunes a Sábados: 10:00 a 19:00 hs</p>
                        <p>📱 WhatsApp: +54 9 3764 81-5689</p>
                    </div>
                    <div className="footer-section">
                        <h3>Enlaces</h3>
                        <div className="footer-links">
                            <a href="#inicio">Inicio</a>
                            <a href="#productos">Productos</a>
                            <a href="#nosotros">Quiénes Somos</a>
                        </div>
                    </div>
                </div>
                <div className="footer-bottom">
                    <p>&copy; 2026 TechStore. Desarrollado con ❤️ por System IA.</p>
                </div>
            </footer>

            <a
                href={buildWhatsAppLink("Hola! Tengo una consulta general sobre un producto.")}
                className="whatsapp-fab"
                title="Chatear con nuestro Bot IA"
                target="_blank"
                rel="noopener noreferrer"
            >
                <MessageCircle size={32} />
            </a>
        </div>
    );
}

export default App;
