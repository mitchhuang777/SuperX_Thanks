import React, { useState, useEffect } from "react";
import { API_BASE_URL } from "../config";
import { Currency } from "lucide-react";

export default function Dashboard() {
  const [selectedVideo, setSelectedVideo] = useState("全部");
  const [selectedAmount, setSelectedAmount] = useState(null);
  const [selectedCurrency, setSelectedCurrency] = useState(null);
  const [amountData, setAmountData] = useState([]);
  const [messages, setMessages] = useState([]);
  const [totalAmount, setTotalAmount] = useState("0.00");
  const [totalDonations, setTotalDonations] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [showScrollTop, setShowScrollTop] = useState(false);
  const [totalVisitors, setTotalVisitors] = useState(0);
  const [dailyVisitors, setDailyVisitors] = useState(0);

  const videoTitleMap = {
    "kOZWQgtqps4": "10年了！227萬訂閱眾量級CROWD「原來不是我的？！」【Andy老師】",
    "hjcTwe5BHYI": "直球對決張家人聲明！【Andy老師】",
  };

  // const CACHE_EXPIRY = 10 * 60 * 1000; // 10 分鐘過期
  const CACHE_EXPIRY = 15 * 1000; // 15 秒過期

  const getCachedData = (key) => {
    const cached = localStorage.getItem(key);
    if (cached) {
      const { data, timestamp } = JSON.parse(cached);
      if (Date.now() - timestamp < CACHE_EXPIRY) {
        return data;
      }
    }
    return null;
  };

  const setCachedData = (key, data) => {
    localStorage.setItem(key, JSON.stringify({ data, timestamp: Date.now() }));
  };


  useEffect(() => {
    const handleScroll = () => {
      if (window.scrollY > 300) {
        setShowScrollTop(true);
      } else {
        setShowScrollTop(false);
      }
    };

    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  // 點擊回到最上面
  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  

  // 取得影片總捐款數據
  useEffect(() => {
    const fetchTotalDonations = async () => {
      setLoading(true);
      const cacheKey = `totalDonations_${selectedVideo}`;

      // 檢查快取
      const cached = getCachedData(cacheKey);
      if (cached) {
        setTotalAmount(cached.totalAmount);
        setTotalDonations(cached.totalDonations);
        setLoading(false);
        return;
      }

      try {
        let url = `${API_BASE_URL}/api/total_donate`;

        if (selectedVideo !== "全部") {
          url += `?video_id=${selectedVideo}`;
        }

        const response = await fetch(url);
        const result = await response.json();

        const data = {
          totalAmount: Number(result.total_donate_twd || 0).toFixed(2),
          totalDonations: result.total_donations || 0,
        };

        setCachedData(cacheKey, data);
        setTotalAmount(Number(result.total_donate_twd || 0).toFixed(2)); // 確保格式化數字
        setTotalDonations(result.total_donations || 0);
      } catch (error) {
        console.error("Failed to fetch total donations:", error);
        setTotalAmount("0.00");
        setTotalDonations(0);
      }
      setLoading(false);
    };

    fetchTotalDonations();
  }, [selectedVideo]); // ✅ 當 `selectedVideo` 改變時，重新請求 API


  useEffect(() => {
    const fetchAmounts = async () => {
      setAmountData([]); // ✅ 切換影片時，先清空資料，避免錯誤

      const cacheKey = `amountData_${selectedVideo}`;
      const cachedData = getCachedData(cacheKey);

      if (cachedData) {
        setAmountData(cachedData);
        return;
      }

      setAmountData([]);
  
      let url = `${API_BASE_URL}/api/super_thanks_summary`;
  
      if (selectedVideo !== "全部") {
        url += `?video_id=${selectedVideo}`;
      }
  
      try {
        const response = await fetch(url);
        const result = await response.json();
  
        if (!result.summary || !Array.isArray(result.summary)) {
          throw new Error("API 回傳的 summary 不是陣列");
        }
  
        setCachedData(cacheKey, result.summary);
        setAmountData(result.summary);
      } catch (error) {
        console.error("Failed to fetch amounts:", error);
        
        // ❗ API 錯誤時，使用快取資料（如果有的話）
        if (cachedData) {
          setAmountData(cachedData);
        } else {
          setAmountData([]); // ❌ 確保沒資料時，才會清空
        }
      }
    };
  
    fetchAmounts();
  }, [selectedVideo]); // ✅ 確保 `selectedVideo` 變更時，重新獲取 `amountData`

  useEffect(() => {
    // 檢查 LocalStorage，確保每天只計算一次
    const lastVisitDate = localStorage.getItem("lastVisitDate");
    const today = new Date().toISOString().split("T")[0];

    const cacheKey = "visitorStats";

    if (lastVisitDate !== today) {
      localStorage.setItem("lastVisitDate", today);

      // API 記錄訪客
      fetch(`${API_BASE_URL}/api/track_visit`, { method: "POST" })
        .then((res) => res.json())
        .catch((err) => console.error("訪客統計錯誤:", err));
    }

    const cachedData = getCachedData(cacheKey);
    if (cachedData) {
      setTotalVisitors(cachedData.totalVisitors);
      setDailyVisitors(cachedData.dailyVisitors);
      return;
    }

    // 取得訪客數據
    fetch(`${API_BASE_URL}/api/visitor_stats`)
      .then((res) => res.json())
      .then((data) => {
        const visitorData = {
          totalVisitors: data.total_visitors,
          dailyVisitors: data.daily_visitors
        };

        setCachedData(cacheKey, visitorData);
        setTotalVisitors(data.total_visitors);
        setDailyVisitors(data.daily_visitors);
      })
      .catch((err) => console.error("無法獲取訪客數據:", err));

      if (cachedData) {
        setTotalVisitors(cachedData.totalVisitors);
        setDailyVisitors(cachedData.dailyVisitors);
      }
  }
  , []);

  const fetchMessages = async (currency, amount) => {
    // 若點擊的金額和當前選中的相同，則收合
    if (selectedAmount === amount && selectedCurrency === currency) {
      setSelectedAmount(null);
      setSelectedCurrency(null);
      setMessages([]);
      return;
    }
  
    setSelectedAmount(amount);
    setSelectedCurrency(currency);
    setLoadingMessages(true);
    setMessages([]); 

    const cacheKey = `messages_${selectedVideo}_${currency}_${amount}`;
    const cachedData = getCachedData(cacheKey);

    if (cachedData) {
      setMessages(cachedData);
      setLoadingMessages(false);
      return;
    }
  
    let url = `${API_BASE_URL}/api/super_thanks/messages?currency_code=${currency}&amount=${amount}`;
  
    if (selectedVideo !== "全部") {
      url += `&video_id=${selectedVideo}`;
    }
  
    try {
      const response = await fetch(url);
      const result = await response.json();
  
      if (!Array.isArray(result)) {
        throw new Error("API 回傳的不是陣列");
      }
  
      const cleanedData = result.map(item => ({
        ...item,
        currency_code: item.currency_code.replace(/^CUR-/, "") 
      }));
      
      setCachedData(cacheKey, cleanedData);
      setMessages(cleanedData);
    } catch (error) {
      console.error("Failed to fetch messages:", error);
      setMessages([]);
    }
  
    setLoadingMessages(false);
  };

  return (
    <div className="flex min-h-screen bg-gray-100 relative">
      {/* 分享功能區塊 */}
      <div className="absolute top-4 right-4 flex space-x-2">

        {/* Threads 分享（目前沒有 API，改為複製連結） */}
        <button
          className="px-4 py-2 bg-gray-700 text-white rounded-md hover:bg-gray-800"
          onClick={() => {
            navigator.clipboard.writeText(window.location.href);
            alert("已複製連結");
          }}
        >
          分享
        </button>
      </div>

      {/* 「滑到最上面」按鈕 */}
      {showScrollTop && (
        <button
          className="fixed bottom-6 right-6 w-12 h-12 bg-gray-300 text-gray-800 rounded-md hover:bg-gray-400 shadow-lg transition duration-300 flex items-center justify-center text-2xl"
          onClick={scrollToTop}
        >
          ⬆
        </button>
      )}

      {/* 左側選擇影片（固定選項） */}
      <div className="w-64 bg-gray-800 text-white p-4">
      <h2 className="text-lg font-bold mb-4">篩選影片</h2>
      <ul>
        {/* 全部影片選項 */}
        <li
          key="all-videos"
          className={`cursor-pointer py-2 ${
            selectedVideo === "全部" ? "font-bold text-yellow-400" : ""
          }`}
          onClick={() => setSelectedVideo("全部")}
        >
          全部影片
        </li>

        {/* 動態載入影片選項 */}
        {Object.entries(videoTitleMap).map(([videoId, title]) => (
          <li
            key={videoId}
            className={`cursor-pointer py-2 ${
              selectedVideo === videoId ? "font-bold text-yellow-400" : ""
            }`}
            onClick={() => setSelectedVideo(videoId)}
          >
            {title}
          </li>
        ))}
      </ul>
    </div>


      {/* 主要內容 */}
      <div className="flex-1 p-6">
        {loading ? (
          <p className="text-center text-lg font-bold text-gray-700">載入中...</p>
        ) : (
          <p className="text-center text-3xl font-semibold text-gray-800 leading-loose">
            {/* 標題（允許換行） */}
            <br />
            <span className="font-extrabold text-4xl break-words">
              {selectedVideo === "全部" 
                ? "全部影片" 
                : videoTitleMap[selectedVideo] || "未知影片"}
            </span>
            <br /><br />
            
            {/* 累積捐款總額 */}
            <span className="text-green-600 font-extrabold text-5xl">
              累積捐款總額：{Number(totalAmount).toLocaleString()} TWD
            </span>
            <br />
            
            {/* 統計筆數 */}
            <span className="text-blue-600 font-semibold text-3xl">
              已統計 <span className="font-extrabold">{Number(totalDonations).toLocaleString()}</span> 筆捐款
            </span>
            <br />
          </p>
        )}

        {/* 金額統計表格 */}
        <table className="w-full mt-6 border-collapse bg-white shadow-md rounded-md">
        <thead>
          <tr className="bg-gray-200 text-gray-700">
            <th className="py-2 px-4 border">幣別</th>
            <th className="py-2 px-4 border">金額</th>
            <th className="py-2 px-4 border">筆數</th>
            <th className="py-2 px-4 border">匯率</th>
            <th className="py-2 px-4 border">幣別總額</th>
            <th className="py-2 px-4 border">台幣總額</th>
            <th className="py-2 px-4 border">操作</th>
          </tr>
        </thead>
        {/* 表格內容 */}
        <tbody>
          {amountData.length === 0 ? (
            <tr>
              <td colSpan="7" className="py-4 text-center text-gray-500">暫無捐款數據</td>
            </tr>
          ) : (
            amountData.map(({ currency_code, amount, occurrence_count, exchange_rate, total_amount, total_amount_twd }, index) => {
              const formattedCurrency = currency_code.replace(/^CUR-/, ""); // ✅ 移除 "CUR-"

              // ✅ 格式化數字，整數不顯示小數點，有小數則保留兩位
              const formatNumber = (num, isExchangeRate = false) => {
                if (isExchangeRate) {
                  return num % 1 === 0 
                    ? num.toLocaleString() // 整數，不顯示小數點
                    : num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 });
                }
                return num % 1 === 0 
                  ? num.toLocaleString() // 整數，不顯示小數點
                  : num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
              };

              return (
                <tr key={`${currency_code}-${amount}-${index}`} className="text-center hover:bg-gray-100">
                  <td className="py-2 px-4 border">{formattedCurrency}</td>
                  <td className="py-2 px-4 border">{formatNumber(amount)}</td>
                  <td className="py-2 px-4 border">{formatNumber(occurrence_count)}</td>
                  <td className="py-2 px-4 border">{formatNumber(exchange_rate, true)}</td>
                  <td className="py-2 px-4 border">{formatNumber(total_amount)}</td>
                  <td className="py-2 px-4 border">{formatNumber(total_amount_twd)}</td>
                  <td className="py-2 px-4 border">
                    <button
                      onClick={() => fetchMessages(currency_code, amount)}
                      className="px-3 py-1 text-white bg-blue-500 hover:bg-blue-600 rounded-md"
                    >
                      {selectedAmount === amount && selectedCurrency === currency_code ? "收合" : "查看"}
                    </button>
                  </td>
                </tr>
              );
            })
          )}
        </tbody>

        </table>

        {/* 顯示留言 */}
        {selectedAmount && selectedCurrency && (
          <div className="mt-6 p-4 border rounded-md bg-gray-50">
            <h2 className="text-xl font-bold text-gray-800 mb-4">
              {selectedCurrency.replace(/^CUR-/, "")} {Number(selectedAmount).toFixed(2)} 的留言：
            </h2>

            {loadingMessages ? (
              <p className="text-gray-600">載入中...</p>
            ) : messages.length === 0 ? (
              <p className="text-gray-600">沒有留言</p>
            ) : (
              <ul className="space-y-4">
                {messages.map((item, index) => (
                  <li
                    key={index}
                    className="p-4 bg-white shadow rounded-md border"
                  >
                    <p className="font-semibold text-gray-800">
                      {item.username}
                    </p>
                    <p className="mt-1 text-gray-700 leading-relaxed">
                      {item.message}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

      {/* 訪客數據 */}
      <div className="text-center text-gray-700 mt-4">
        <p className="text-lg font-semibold">
          今日訪客數： <span className="text-blue-600">{Number(dailyVisitors).toLocaleString()}</span>
        </p>
        <p className="text-lg font-semibold">
          總訪客數： <span className="text-green-600">{Number(totalVisitors).toLocaleString()}</span>
        </p>
      </div>

        {/* 開發者資訊 & 支援連結 */}
        <div className="mt-12 p-6 bg-gray-100 border-t flex flex-col md:flex-row justify-center items-center space-y-2 md:space-y-0 md:space-x-4 text-gray-700 text-sm">
          {/* Mitch 變成超連結，指向 Threads */}
          <p>
            © {new Date().getFullYear()}{" "}
            <a 
              href="https://www.threads.net/@i.g._.mitch" 
              target="_blank" 
              rel="noopener noreferrer"
              className="text-blue-500 hover:underline"
            >
              Mitch
            </a>. All rights reserved.
          </p>

          {/* Buy Me a Coffee */}
          <a 
            href="https://buymeacoffee.com/huangmitch" 
            target="_blank" 
            rel="noopener noreferrer"
            className="px-4 py-2 bg-yellow-400 text-black rounded-md hover:bg-yellow-500 transition duration-300 text-sm"
          >
            ☕ Buy Me a Coffee
          </a>
        </div>

      </div>
    </div>
  );
}
