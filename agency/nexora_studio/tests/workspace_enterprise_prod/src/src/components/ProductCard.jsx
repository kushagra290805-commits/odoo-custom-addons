import React from 'react';

export default function ProductCard({ product }) {
  const { title, price, image, description } = product;
  return (
    <article className="product-card" aria-label={title}>
      <img src={image} alt={title || ''} loading="lazy" />
      <h3>{title}</h3>
      <p>{description}</p>
      <span className="product-card__price">${price}</span>
    </article>
  );
}
