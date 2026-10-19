(() => {
  const pairs = [
    ["Maklersiz uy toping", "Найдите жильё без посредников"],
    ["UyTop’ga xush kelibsiz", "Добро пожаловать в UyTop"],
    ["Bu Mini App’ni Telegram ichidagi bot tugmasidan oching.", "Откройте Mini App кнопкой в чате Telegram-бота."],
    ["Telegram’ga o‘tish", "Перейти в Telegram"],
    ["Asosiy", "Главная"], ["Qidirish", "Поиск"], ["E’lon berish", "Разместить"],
    ["Sevimlilar", "Избранное"], ["Profil", "Профиль"],
    ["Tavsiya etilgan e’lonlar", "Рекомендуемые объявления"], ["Barchasi →", "Все →"],
    ["⌕   Tuman yoki uy turini qidiring", "⌕   Выберите район или тип жилья"],
    ["Barchasi", "Все"], ["Kvartira", "Квартира"], ["Xonadon", "Жильё"], ["Uy", "Дом"], ["Yotoqxona", "Общежитие"],
    ["Ijara", "Аренда"], ["Sotuv", "Продажа"], ["Kunlik ijara", "Посуточно"],
    ["E’lonlar", "Объявления"], ["Natijalar", "Результаты"], ["Qidiruv", "Поиск"],
    ["Tumanni tanlang", "Выберите район"], ["Tuman", "Район"], ["Uy turi", "Тип жилья"],
    ["Narxdan", "Цена от"], ["Narxgacha", "Цена до"], ["Xona soni", "Комнат"],
    ["Qidirish", "Найти"], ["Qidiruvni saqlash", "Сохранить поиск"], ["Saqlangan qidiruv nomi:", "Название сохранённого поиска:"],
    ["Saqlangan qidiruvlar", "Сохранённые поиски"], ["Qidiruv saqlandi.", "Поиск сохранён."],
    ["Bu filtrlar bo‘yicha e’lon topilmadi.", "По этим фильтрам объявлений нет."],
    ["Yana ko‘rsatish", "Показать ещё"], ["Ko‘proq ko‘rsatish", "Показать ещё"],
    ["Batafsil", "Подробнее"], ["Xaritada ko‘rish", "Посмотреть на карте"],
    ["Bog‘lanish", "Связаться"], ["Shikoyat yuborish", "Пожаловаться"], ["Shikoyat yuborildi.", "Жалоба отправлена."],
    ["Uy egasining Telegram username’i yo‘q.", "У владельца нет Telegram-имени пользователя."],
    ["Sevimlilarga saqlash", "В избранное"], ["Sevimlilarga saqlandi.", "Добавлено в избранное."],
    ["Sevimli e’lonlar", "Избранные объявления"], ["Saqlangan e’lon yo‘q.", "Сохранённых объявлений нет."],
    ["Bildirishnomalarni olish", "Получать уведомления"], ["Mening e’lonlarim", "Мои объявления"],
    ["Ko‘rilgan e’lonlar", "Просмотренные объявления"], ["Hozircha e’lon joylashtirmagansiz.", "Вы пока не размещали объявления."],
    ["Yordam", "Помощь"], ["E’lon bo‘yicha savol yoki shikoyat uchun botdagi /help buyrug‘idan foydalaning.", "По вопросам и жалобам используйте команду /help в боте."],
    ["E’lon joylashtirish", "Разместить объявление"], ["Bitim turi", "Тип сделки"], ["Uy turi", "Тип жилья"],
    ["Mahalla", "Махалля"], ["Manzil (ixtiyoriy)", "Адрес (необязательно)"], ["Valyuta", "Валюта"],
    ["Maydon (m²)", "Площадь (м²)"], ["Qavat", "Этаж"], ["Qavatlar soni", "Этажей в доме"],
    ["E’lon sarlavhasi", "Заголовок объявления"], ["Tavsif", "Описание"], ["Qulayliklar (vergul bilan)", "Удобства (через запятую)"],
    ["Rasmlar (12 tagacha)", "Фотографии (до 12)"], ["Rasmlar Telegram’da saqlanadi.", "Фотографии сохраняются в Telegram."],
    ["Telefon raqami", "Номер телефона"], ["Telefon raqamimni ko‘rsatishga roziman", "Согласен показать номер телефона"],
    ["Keyingisi →", "Далее →"], ["Orqaga", "Назад"], ["Bekor qilish", "Отмена"], ["Saqlash", "Сохранить"],
    ["Moderatsiyaga yuborish", "Отправить на модерацию"], ["Yakuniy ko‘rib chiqish", "Итоговая проверка"],
    ["Bosqich", "Шаг"], ["Qayta urinish", "Повторить"],
    ["Qoralama", "Черновик"], ["Tekshiruvda", "На проверке"], ["Faol", "Активно"], ["Rad etilgan", "Отклонено"], ["Band", "Сдано"], ["Arxiv", "Архив"],
    ["Rasm Telegram’da saqlandi.", "Фотография сохранена в Telegram."], ["Sozlama saqlandi.", "Настройка сохранена."],
    ["Bu e’lon endi mavjud emas.", "Это объявление больше недоступно."], ["Uy egasi bilan bog‘lanish ma’lumoti mavjud emas.", "Контактные данные владельца отсутствуют."],
    ["Uy egasi bilan bog‘lanish usulini tanlang:", "Выберите способ связи с владельцем:"],
    ["Telefon raqamini ko‘rsatish", "Показать номер телефона"], ["Uy egasi telefon raqamini ko‘rsatishga rozilik bermagan.", "Владелец не разрешил показывать номер телефона."],
    ["Raqamni ko‘rishni xohlaysizmi?", "Хотите увидеть номер телефона?"], ["Uy egasi telefoni:", "Телефон владельца:"],
    ["Botdagi /help buyrug‘idan foydalaning.", "Используйте команду /help в боте."],
  ];
  const originals = new WeakMap();
  const attrs = new WeakMap();
  let lang = localStorage.getItem("uytop_lang") === "ru" ? "ru" : "uz";
  function translate(value) {
    if (lang !== "ru") return value;
    return [...pairs].sort((a,b)=>b[0].length-a[0].length).reduce((text,[uz,ru])=>text.replaceAll(uz,ru),value);
  }
  function apply(root = document.body) {
    const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
    let node;
    while((node=walker.nextNode())) {
      if(!node.nodeValue.trim()) continue;
      let entry=originals.get(node);
      if(!entry || node.nodeValue!==entry.rendered) { entry={base:node.nodeValue,rendered:node.nodeValue}; originals.set(node,entry); }
      const result=translate(entry.base);
      if(result!==node.nodeValue) { entry.rendered=result; node.nodeValue=result; }
    }
    root.querySelectorAll?.("[placeholder],[aria-label],[title]").forEach(el=>{
      let map=attrs.get(el); if(!map){map={};attrs.set(el,map);}
      for(const key of ["placeholder","aria-label","title"]) if(el.hasAttribute(key)) {
        const value=el.getAttribute(key);
        if(map[key]===undefined || value!==map[key+"Rendered"]) map[key]=value;
        const result=translate(map[key]);
        if(value!==result){map[key+"Rendered"]=result;el.setAttribute(key,result);}
      }
    });
    const button=document.getElementById("language-switch"); if(button) button.textContent=lang.toUpperCase();
    document.documentElement.lang=lang;
  }
  function set(value) { lang=value==="ru"?"ru":"uz";localStorage.setItem("uytop_lang",lang);apply(); }
  window.UyTopLang={get:()=>lang,set,apply,toggle:()=>set(lang==="uz"?"ru":"uz")};
  document.addEventListener("DOMContentLoaded",()=>apply());
  new MutationObserver(records=>records.forEach(record=>{
    if(record.type==="characterData") apply(record.target.parentElement||document.body);
    else record.addedNodes.forEach(node=>{if(node.nodeType===Node.ELEMENT_NODE)apply(node);else if(node.nodeType===Node.TEXT_NODE)apply(node.parentElement||document.body);});
  })).observe(document.documentElement,{childList:true,subtree:true,characterData:true});
  apply();
})();