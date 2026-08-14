import React, { useMemo } from 'react';
import ProductCard from '../components/ProductCard';

const PRODUCTS = [
  { id: 1, title: 'Widget', price: 10, image: '/w.png', description: 'A widget' },
  { id: 2, title: 'Gadget', price: 20, image: '/g.png', description: 'A gadget' }
];

export default function Shop() {
  const products = useMemo(() => PRODUCTS, []);
  return (
    <main>
      <h1>Shop</h1>
      <ul className="product-grid" role="list">
        {products.map(p => (
          <li key={p.id}>
            <ProductCard product={p} />
          </li>
        ))}
      </ul>
    </main>
  );
}
