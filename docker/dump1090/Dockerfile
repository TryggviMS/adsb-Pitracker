FROM debian:bookworm

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    build-essential cmake git pkg-config libusb-1.0-0-dev \
    libncurses5-dev libncursesw5-dev ca-certificates usbutils \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get purge -y librtlsdr0 librtlsdr-dev rtl-sdr || true && \
    apt-get autoremove -y || true

WORKDIR /opt
RUN git clone https://github.com/rtlsdrblog/rtl-sdr-blog.git && \
    cd rtl-sdr-blog && \
    mkdir build && cd build && \
    cmake .. -DINSTALL_UDEV_RULES=OFF -DDETACH_KERNEL_DRIVER=ON && \
    make -j$(nproc) && make install && ldconfig

WORKDIR /opt
RUN git clone https://github.com/mutability/dump1090.git && \
    cd dump1090 && make -j$(nproc)

WORKDIR /opt/dump1090
EXPOSE 8080

CMD ["./dump1090", \
    "--device-type", "rtlsdr", \
    "--net", \
    "--write-json", "/data", \
    "--json-location-accuracy", "2"]
