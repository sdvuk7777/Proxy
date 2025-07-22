const express = require('express');
const request = require('request');
const app = express();

app.get('/proxy', (req, res) => {
    const targetUrl = req.query.url;
    if (!targetUrl) {
        res.status(400).send('Missing URL');
        return;
    }

    request({
        url: targetUrl,
        headers: {
            'Referer': 'https://appx-play.akamai.net.in/',
            'Origin': 'https://appx-play.akamai.net.in/'
        }
    }).pipe(res);
});

app.listen(3000, () => {
    console.log('Proxy running on port 3000');
});