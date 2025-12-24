const express = require("express");
const router = express.Router();

// Temporary in-memory users (for hackathon demo)
let users = [];

/**
 * REGISTER
 */
router.post("/register", (req, res) => {
  const { name, email, password, role, location, produceType } = req.body;

  if (!name || !email || !password || !role) {
    return res.status(400).json({ message: "Missing fields" });
  }

  const userExists = users.find(u => u.email === email);
  if (userExists) {
    return res.status(400).json({ message: "User already exists" });
  }

  const newUser = {
    id: users.length + 1,
    name,
    email,
    password, // (plain text for demo only)
    role,
    location,
    produceType: role === "farmer" ? produceType : null
  };

  users.push(newUser);
  res.status(201).json({ message: "User registered successfully" });
});

/**
 * LOGIN
 */
router.post("/login", (req, res) => {
  const { email, password } = req.body;

  const user = users.find(
    u => u.email === email && u.password === password
  );

  if (!user) {
    return res.status(401).json({ message: "Invalid credentials" });
  }

  res.json({
    message: "Login successful",
    role: user.role,
    name: user.name
  });
});

module.exports = router;
