// src/components/Header.js

import React from 'react';

const Header = ({ title, subTitle }) => {
  return (
    <header className="flex items-center justify-between p-4 bg-white shadow-md">
      <h1 className="text-xl font-bold">{title}</h1>
      {subTitle && (
        <p className="text-sm text-gray-600">{subTitle}</p>
      )}
      {/* Add more styles or additional elements as needed */}
    </header>
  );
};

export default Header;
```

This is a basic React component for a responsive header that you can extend based on your specific design requirements. It includes basic styling to ensure it's responsive and fits different screen sizes. You might need to adjust the CSS or add more styles depending on your project's overall design system.