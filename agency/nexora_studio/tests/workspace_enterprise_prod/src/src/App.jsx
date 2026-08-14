import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Shop from './pages/Shop';

export default function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Shop />} />
      </Routes>
    </Router>
  );
}