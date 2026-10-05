package eu.org.vidsave.app;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.DownloadManager;
import android.content.ActivityNotFoundException;
import android.content.Context;
import android.content.Intent;
import android.net.ConnectivityManager;
import android.net.NetworkCapabilities;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.DownloadListener;
import android.webkit.URLUtil;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

public class MainActivity extends Activity {

    private WebView web;
    private ProgressBar progress;
    private View errorBox;
    private TextView errorHint;
    private ValueCallback<Uri[]> filePathCallback;
    private boolean triedFallback = false;
    private static final int FILE_CHOOSER = 1001;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        web = findViewById(R.id.web);
        progress = findViewById(R.id.progress);
        errorBox = findViewById(R.id.errorBox);
        errorHint = findViewById(R.id.errorHint);
        Button retry = findViewById(R.id.retry);
        Button openBrowser = findViewById(R.id.openBrowser);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE);
        s.setUserAgentString(s.getUserAgentString() + " VidSaveApp/1.0");

        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, true);

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return handleUrl(request.getUrl().toString());
            }

            @Override
            public void onPageStarted(WebView view, String url, android.graphics.Bitmap favicon) {
                progress.setVisibility(View.VISIBLE);
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                progress.setVisibility(View.GONE);
                errorBox.setVisibility(View.GONE);
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) {
                    showError();
                }
            }
        });

        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                progress.setVisibility(newProgress < 100 ? View.VISIBLE : View.GONE);
                progress.setProgress(newProgress);
            }

            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> cb, FileChooserParams params) {
                filePathCallback = cb;
                try {
                    startActivityForResult(params.createIntent(), FILE_CHOOSER);
                    return true;
                } catch (ActivityNotFoundException e) {
                    filePathCallback = null;
                    return false;
                }
            }
        });

        web.setDownloadListener(new DownloadListener() {
            @Override
            public void onDownloadStart(String url, String userAgent, String contentDisposition,
                                        String mimeType, long contentLength) {
                try {
                    String name = URLUtil.guessFileName(url, contentDisposition, mimeType);
                    if (name.toLowerCase().endsWith(".apk")) {
                        mimeType = "application/vnd.android.package-archive";
                    }
                    DownloadManager.Request req = new DownloadManager.Request(Uri.parse(url));
                    req.setMimeType(mimeType);
                    req.addRequestHeader("User-Agent", userAgent);
                    req.addRequestHeader("Cookie", CookieManager.getInstance().getCookie(url));
                    req.setTitle(name);
                    req.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                    req.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, name);
                    DownloadManager dm = (DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE);
                    if (dm != null) {
                        dm.enqueue(req);
                        Toast.makeText(MainActivity.this, "ডাউনলোড শুরু হয়েছে…", Toast.LENGTH_SHORT).show();
                    }
                } catch (Exception e) {
                    openExternal(url);
                }
            }
        });

        retry.setOnClickListener(v -> {
            errorBox.setVisibility(View.GONE);
            web.reload();
        });

        openBrowser.setOnClickListener(v -> openExternal(getString(R.string.home_url)));

        errorHint.setText(getString(R.string.error_hint));

        String home = getString(R.string.home_url);
        if (savedInstanceState != null) {
            web.restoreState(savedInstanceState);
        } else {
            web.loadUrl(home);
        }
    }

    private boolean isOnline() {
        try {
            ConnectivityManager cm = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
            if (cm == null) return true;
            NetworkCapabilities nc = cm.getNetworkCapabilities(cm.getActiveNetwork());
            return nc != null && nc.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET);
        } catch (Exception e) {
            return true;
        }
    }

    private void showError() {
        if (!triedFallback && !isOnline()) {
            errorHint.setText("ইন্টারনেট সংযোগ নেই। Wi-Fi বা মোবাইল ডেটা চালু করুন।");
            errorBox.setVisibility(View.VISIBLE);
            return;
        }
        String home = getString(R.string.home_url);
        String fallback = getString(R.string.fallback_url);
        if (!triedFallback && fallback != null && !fallback.isEmpty()
                && !fallback.equals(home)) {
            triedFallback = true;
            errorHint.setText("প্রধান ঠিকানা পাওয়া যায়নি, বিকল্প ঠিকানায় চেষ্টা করা হচ্ছে…");
            errorBox.setVisibility(View.VISIBLE);
            web.loadUrl(fallback);
            return;
        }
        errorHint.setText(getString(R.string.error_hint));
        errorBox.setVisibility(View.VISIBLE);
    }

    private boolean handleUrl(String url) {
        if (url.startsWith("http://") || url.startsWith("https://")) {
            if (sameHost(url, getString(R.string.home_url))
                    || sameHost(url, getString(R.string.fallback_url))) {
                return false;
            }
            openExternal(url);
            return true;
        }
        if (url.startsWith("mailto:") || url.startsWith("tel:") || url.startsWith("whatsapp:")
                || url.startsWith("tg:") || url.startsWith("intent:")) {
            openExternal(url);
            return true;
        }
        return false;
    }

    private boolean sameHost(String a, String b) {
        try {
            String ha = Uri.parse(a).getHost();
            String hb = Uri.parse(b).getHost();
            return ha != null && ha.equalsIgnoreCase(hb);
        } catch (Exception e) {
            return false;
        }
    }

    private void openExternal(String url) {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
        } catch (Exception ignored) {
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode == FILE_CHOOSER) {
            if (filePathCallback != null) {
                filePathCallback.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(resultCode, data));
                filePathCallback = null;
            }
            return;
        }
        super.onActivityResult(requestCode, resultCode, data);
    }

    @Override
    public void onBackPressed() {
        if (errorBox.getVisibility() == View.VISIBLE) {
            errorBox.setVisibility(View.GONE);
            return;
        }
        if (web.canGoBack()) {
            web.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        web.saveState(outState);
    }
}
