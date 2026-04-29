import { Refine } from "@refinedev/core";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { dataProvider } from "./providers";

function App() {
  return (
    <BrowserRouter>
      <Refine dataProvider={dataProvider}>
        <Routes>
          <Route path="/" element={<div>有证慧催 MVP</div>} />
        </Routes>
      </Refine>
    </BrowserRouter>
  );
}

export default App;
