import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import NativeApp from './NativeApp';
import './styles.css';
createRoot(document.getElementById('root')!).render(<StrictMode><NativeApp /></StrictMode>);
