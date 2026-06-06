import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const SESSION_KEY = "etsywatch_email";

export const getSession = () => localStorage.getItem(SESSION_KEY);
export const setSession = (email) => localStorage.setItem(SESSION_KEY, email);
export const clearSession = () => localStorage.removeItem(SESSION_KEY);

const client = axios.create({ baseURL: API });

client.interceptors.request.use((config) => {
  const email = getSession();
  if (email) {
    config.headers["X-User-Email"] = email;
  }
  return config;
});

export default client;
