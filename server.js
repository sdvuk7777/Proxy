const express = require('express');
const axios = require('axios');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const jwt = require('jsonwebtoken');
const app = express();

const PORT = process.env.PORT || 3000;
const TOKENS_FILE = path.join(__dirname, 'tokens.json');
const MAX_REQUESTS_PER_TOKEN = 5000;
const REQUEST_DELAY_MS = 4000; // 4 seconds

// Initialize tokens file if not exists
if (!fs.existsSync(TOKENS_FILE)) {
    fs.writeFileSync(TOKENS_FILE, JSON.stringify({}));
}

// Token rotation pool
const authTokens = [
    "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpZCI6IjUxNzA3NyIsImVtYWlsIjoidml2ZWtrYXNhbmE0QGdtYWlsLmNvbSIsInRpbWVzdGFtcCI6MTcyNjkzNzA4OX0.NM1SbOjDFZCLinFi66jKxwRQPgLWFN-_SAMgcPWvfk4",
    "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpZCI6IjUxNzA3NyIsImVtYWlsIjoidml2ZWtrYXNhbmE0QGdtYWlsLmNvbSIsInRpbWVzdGFtcCI6MTcyNjU2MTM2Nn0.XimZ3jxS_j-7B4BpTUR9ZeeaJ8at-ROfPYMdm0GCf6I"
];

let currentTokenIndex = 0;

function getNextAuthToken() {
    currentTokenIndex = (currentTokenIndex + 1) % authTokens.length;
    return authTokens[currentTokenIndex];
}

// AES-128-CBC Decryption Function
function decrypt(encryptedBase64) {
    try {
        if (!encryptedBase64 || typeof encryptedBase64 !== 'string') return '';

        const parts = encryptedBase64.split(':');
        if (parts.length < 1) return '';

        const encryptedData = parts[0].trim();

        const enc = Buffer.from(encryptedData, 'base64');
        const key = Buffer.from('638udh3829162018', 'utf8');
        const iv = Buffer.from('fedcba9876543210', 'utf8');

        const decipher = crypto.createDecipheriv('aes-128-cbc', key, iv);
        decipher.setAutoPadding(false);

        let decrypted = Buffer.concat([decipher.update(enc), decipher.final()]);

        // Remove PKCS#7 padding
        const pad = decrypted[decrypted.length - 1];
        if (pad > 0 && pad <= 16) {
            decrypted = decrypted.slice(0, -pad);
        }

        return decrypted.toString('utf8').trim();
    } catch (err) {
        console.error("❌ Decryption error:", err.message);
        return '';
    }
}

// Validate JWT token
function validateToken(token) {
    try {
        const decoded = jwt.decode(token);
        if (!decoded) return false;

        // Check header
        const header = jwt.decode(token, { complete: true })?.header;
        if (!header || header.typ !== 'JWT') return false;

        // Check payload structure
        if (!decoded.id || !decoded.email || !decoded.timestamp) return false;

        return true;
    } catch (err) {
        return false;
    }
}

// Request Token Management System
async function handleRequestToken(req, res, next) {
    const { token } = req.query;

    if (!token) {
        return res.status(400).json({ 
            status: 400,
            error: "Token parameter is required" 
        });
    }

    // Validate token structure
    if (!validateToken(token)) {
        return res.status(400).json({ 
            status: 400,
            error: "Invalid token format" 
        });
    }

    const tokensData = JSON.parse(fs.readFileSync(TOKENS_FILE));
    const currentDate = new Date().toISOString().split('T')[0];

    // Initialize token data if not exists
    if (!tokensData[token]) {
        tokensData[token] = {
            count: 0,
            lastRequest: 0,
            dateAdded: currentDate
        };
    } else if (tokensData[token].dateAdded !== currentDate) {
        // Reset counter for new day
        tokensData[token].count = 0;
        tokensData[token].dateAdded = currentDate;
    }

    // Check rate limits
    if (tokensData[token].count >= MAX_REQUESTS_PER_TOKEN) {
        return res.status(429).json({ 
            status: 429,
            error: "Daily request limit exceeded for this token" 
        });
    }

    // Check request delay
    const now = Date.now();
    const timeSinceLastRequest = now - tokensData[token].lastRequest;

    if (timeSinceLastRequest < REQUEST_DELAY_MS) {
        // Implement padding delay
        const delayTime = REQUEST_DELAY_MS - timeSinceLastRequest;
        await new Promise(resolve => setTimeout(resolve, delayTime));
    }

    // Update token usage
    tokensData[token].count += 1;
    tokensData[token].lastRequest = Date.now();
    fs.writeFileSync(TOKENS_FILE, JSON.stringify(tokensData, null, 2));

    next();
}

// Cleanup old tokens (run daily)
function cleanupTokens() {
    const currentDate = new Date().toISOString().split('T')[0];
    const tokensData = JSON.parse(fs.readFileSync(TOKENS_FILE));

    for (const token in tokensData) {
        if (tokensData[token].dateAdded !== currentDate) {
            delete tokensData[token];
        }
    }

    fs.writeFileSync(TOKENS_FILE, JSON.stringify(tokensData, null, 2));
}

// Schedule daily cleanup
setInterval(cleanupTokens, 24 * 60 * 60 * 1000); // Run every 24 hours

// New endpoint to view tokens data
app.get('/view-tokens', (req, res) => {
    try {
        if (!fs.existsSync(TOKENS_FILE)) {
            return res.status(404).json({
                status: 404,
                error: "Tokens file not found"
            });
        }

        const tokensData = JSON.parse(fs.readFileSync(TOKENS_FILE));

        // Calculate statistics
        const totalTokens = Object.keys(tokensData).length;
        let totalRequests = 0;
        const today = new Date().toISOString().split('T')[0];

        Object.values(tokensData).forEach(token => {
            totalRequests += token.count;
        });

        res.json({
            status: 200,
            data: {
                tokens: tokensData,
                statistics: {
                    total_tokens: totalTokens,
                    total_requests: totalRequests,
                    date: today
                }
            }
        });
    } catch (err) {
        console.error("❌ Error viewing tokens:", err.message);
        res.status(500).json({
            status: 500,
            error: "Failed to read tokens data"
        });
    }
});

// Video Details Endpoint
app.get('/video-details', handleRequestToken, async (req, res) => {
    const { userid, course_id, video_id, token } = req.query;

    if (!userid || !course_id || !video_id || !token) {
        return res.status(400).json({ 
            status: 400,
            data: [],
            error: "Missing required query parameters." 
        });
    }

    const headers = {
        "Client-Service": "Appx",
        "source": "website",
        "Auth-Key": "appxapi",
        "Authorization": getNextAuthToken(),
        "User-ID": userid
    };

    const API_BASE = "https://rozgarapinew.teachx.in";
    const url = `${API_BASE}/get/fetchVideoDetailsById?course_id=${course_id}&video_id=${video_id}&ytflag=0&folder_wise_course=0`;

    try {
        const response = await axios.get(url, { headers });
        const data = response.data.data;

        if (!data) {
            return res.status(404).json({ 
                status: 404,
                data: [],
                error: "No data found for this video" 
            });
        }

        const decryptedPdf1 = data.pdf_link ? decrypt(data.pdf_link) : '';
        const decryptedPdf2 = data.pdf_link2 ? decrypt(data.pdf_link2) : '';

        const videoDetails = {
            title: data.Title || "",
            thumbnail: data.thumbnail || "",
            date_and_time: data.date_and_time || "",
            qualities: {},
            primary_download_url: "",
            youtube_id: "",
            pdf_link: decryptedPdf1,
            pdf_link2: decryptedPdf2
        };

        // Decrypt video download qualities
        if (Array.isArray(data.download_links)) {
            data.download_links.forEach(link => {
                if (link.path) {
                    const quality = link.quality || "unknown";
                    videoDetails.qualities[quality] = decrypt(link.path);
                }
            });
        }

        // Decrypt primary download URL
        if (data.download_link) {
            videoDetails.primary_download_url = decrypt(data.download_link);
        }

        // YouTube ID (if present)
        if (data.video_id) {
            videoDetails.youtube_id = "https://youtu.be/" + decrypt(data.video_id);
        }

        res.json({
            status: 200,
            data: [videoDetails]
        });

    } catch (err) {
        console.error("❌ Error in API:", err.message);
        res.status(500).json({ 
            status: 500,
            data: [],
            error: `Error occurred: ${err.message}` 
        });
    }
});

// Live Classes Endpoint - Only returns live classes with status key
app.get('/live', handleRequestToken, async (req, res) => {
    const { userid, course_id, token } = req.query;

    if (!userid || !course_id || !token) {
        return res.status(400).json({ 
            status: 400,
            data: [],
            error: "Missing required query parameters (userid, course_id, and token)." 
        });
    }

    const headers = {
        "Client-Service": "Appx",
        "source": "website",
        "Auth-Key": "appxapi",
        "Authorization": getNextAuthToken(),
        "User-ID": userid
    };

    const API_BASE = "https://rozgarapinew.teachx.in";
    const url = `${API_BASE}/get/live_upcoming_course_classv2?courseid=${course_id}&start=-1`;

    try {
        const response = await axios.get(url, { headers });
        const responseData = response.data.data;

        if (!responseData || !responseData.live || responseData.live.length === 0) {
            return res.status(404).json({ 
                status: 404,
                data: [],
                error: "No live classes currently available" 
            });
        }

        const liveClasses = [];

        // Process only live classes
        responseData.live.forEach(classData => {
            const classInfo = {
                status: "live",  // Status key added here
                id: classData.id || "",
                title: classData.Title || "",
                thumbnail: classData.thumbnail || "",
                date_and_time: classData.date_and_time || "",
                qualities: {},
                low_latency_enabled: classData.low_latency_enabled || false,
                live_status: classData.live_status || "1"
            };

            // Decrypt all quality streams
            if (Array.isArray(classData.livestream_links)) {
                classData.livestream_links.forEach(link => {
                    if (link.path && link.quality) {
                        const quality = link.quality.replace(' Quality', '').toLowerCase();
                        classInfo.qualities[quality] = decrypt(link.path);
                    }
                });
            }

            // Decrypt primary stream URL
            if (classData.file_link) {
                classInfo.primary_stream_url = decrypt(classData.file_link);
            }

            liveClasses.push(classInfo);
        });

        res.json({
            status: 200,
            data: liveClasses
        });

    } catch (err) {
        console.error("❌ Error in Live API:", err.message);
        res.status(500).json({ 
            status: 500,
            data: [],
            error: `Error occurred: ${err.message}` 
        });
    }
});

app.listen(PORT, () => {
    console.log(`🚀 Server running on port ${PORT}`);
    cleanupTokens(); // Initial cleanup
});